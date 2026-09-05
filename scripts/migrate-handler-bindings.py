#!/usr/bin/env python3
"""Offline, backed-up migration from versioned to name/contract Handler refs.

Run without --apply first. Stop all Orbit writers before --apply. Historical
workflow version numbers are preserved. A hash collision aborts the migration.
"""
import argparse
import json
from pathlib import Path
import sqlite3
import sys

import yaml
from orbit.workflow.domain.ir_schema import workflow_ir_from_primitive
from orbit.workflow.domain.serialization import canonical_json, definition_hash


def strip_versions(value):
    changed = False
    if isinstance(value, dict):
        handler = value.get('handler')
        if isinstance(handler, dict) and 'version' in handler:
            handler.pop('version')
            changed = True
        for child in value.values():
            changed = strip_versions(child) or changed
    elif isinstance(value, list):
        for child in value:
            changed = strip_versions(child) or changed
    return changed


def source_without_versions(source, fmt):
    if not source:
        return source
    document = json.loads(source) if fmt in {'json', 'ui'} else yaml.safe_load(source)
    if not strip_versions(document):
        return source
    return (json.dumps(document, ensure_ascii=False, indent=2) if fmt in {'json', 'ui'}
            else yaml.safe_dump(document, allow_unicode=True, sort_keys=False))


def planned_versions(connection):
    """Each published version as it will be, with the hash it lands on.

    Computed for every row, not only the ones that change: a row this
    migration leaves alone still occupies its hash, and a rewritten one can
    land on it.
    """

    plans = []
    for row in list(connection.execute('SELECT rowid,* FROM workflow_versions')):
        graph = json.loads(row['canonical_ir_json'])
        changed = strip_versions(graph)
        source = source_without_versions(row['source_text'], row['source_format'])
        rewritten = changed or source != row['source_text']
        ir = workflow_ir_from_primitive(graph) if rewritten else None
        digest = definition_hash(ir).value if rewritten else row['definition_hash']
        plans.append((row, ir, digest, source, rewritten))
    return plans


def refuse_collisions(plans, columns):
    """Say which versions become the same definition, before touching any.

    Two published versions of one workflow that differed only in the Handler
    build *are* the same definition once the build is gone, and
    `UNIQUE (workflow_id, definition_hash)` says so — as an IntegrityError
    naming a constraint, which tells an operator nothing about which workflow
    to look at. Not a corner case either: it is exactly what `workflow.rebind`
    produces, so a database is more likely to hit this the more its owner
    repaired drift the supported way.

    Answered here, before the immutability triggers come off, so a refusal
    leaves nothing to undo.
    """

    landing = {}
    for row, _ir, digest, _source, _rewritten in plans:
        workflow = row['workflow_id'] if 'workflow_id' in columns else ''
        label = row['version'] if 'version' in columns else row['rowid']
        landing.setdefault((workflow, digest), []).append(label)
    clashes = {
        key: sorted(labels, key=str)
        for key, labels in landing.items() if len(labels) > 1
    }
    if not clashes:
        return
    lines = [
        f"  {workflow or '(unnamed workflow)'}: versions "
        + ", ".join(str(label) for label in labels)
        for (workflow, _digest), labels in sorted(clashes.items(), key=str)
    ]
    raise ValueError(
        "these published versions become the same definition once the Handler "
        "build number is removed, and a workflow cannot hold one definition "
        "twice:\n" + "\n".join(lines)
        + "\n\nThey differ only in the build they were compiled against, which "
        "this migration is removing. Decide which one survives — delete or "
        "renumber the others — and run the migration again. Nothing has been "
        "changed."
    )


def migrate(connection):
    connection.row_factory = sqlite3.Row
    tables = {r[0] for r in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    counts = {}
    plans = []
    if 'workflow_versions' in tables:
        columns = {r[1] for r in connection.execute('PRAGMA table_info(workflow_versions)')}
        plans = planned_versions(connection)
        refuse_collisions(plans, columns)
    # Only this explicit offline migration may update published immutable rows.
    triggers = list(connection.execute("SELECT name,sql FROM sqlite_master WHERE type='trigger' AND tbl_name='workflow_versions'"))
    for row in triggers:
        connection.execute('DROP TRIGGER "' + row['name'].replace('"', '""') + '"')
    for row, ir, digest, source, rewritten in plans:
        if rewritten:
            connection.execute('UPDATE workflow_versions SET canonical_ir_json=?,definition_hash=?,source_text=? WHERE rowid=?',
                               (canonical_json(ir), digest, source, row['rowid']))
            counts['workflow_versions'] = counts.get('workflow_versions', 0) + 1
    for row in triggers:
        connection.execute(row['sql'])
    if 'langgraph_runs' in tables:
        for row in list(connection.execute('SELECT rowid,graph_snapshot_json FROM langgraph_runs WHERE graph_snapshot_json IS NOT NULL')):
            graph = json.loads(row['graph_snapshot_json'])
            if strip_versions(graph):
                ir = workflow_ir_from_primitive(graph)
                connection.execute('UPDATE langgraph_runs SET graph_snapshot_json=? WHERE rowid=?', (canonical_json(ir), row['rowid']))
                counts['run_snapshots'] = counts.get('run_snapshots', 0) + 1
    if 'workflow_drafts' in tables:
        for row in list(connection.execute('SELECT rowid,* FROM workflow_drafts')):
            source = source_without_versions(row['source_text'], row['source_format'])
            if source != row['source_text']:
                connection.execute('UPDATE workflow_drafts SET source_text=?,source_hash=?,validation_status=?,validated_source_hash=NULL,validated_definition_hash=NULL WHERE rowid=?',
                                   (source, definition_hash({"draft_source": source}).value, 'dirty', row['rowid']))
                counts['drafts'] = counts.get('drafts', 0) + 1
    if connection.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
        raise ValueError('database integrity check failed')
    return counts


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('databases', type=Path, nargs='+')
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--backup-dir', type=Path)
    args = parser.parse_args()
    if args.apply and args.backup_dir is None:
        parser.error('--apply requires --backup-dir')
    # Preflight every database before touching any of them.
    for path in args.databases:
        with sqlite3.connect(f'file:{path.resolve()}?mode=ro', uri=True) as source:
            memory = sqlite3.connect(':memory:')
            source.backup(memory)
            memory.execute('BEGIN')
            try:
                counts = migrate(memory)
            except ValueError as refusal:
                # A refusal is an answer, not a crash: the operator has a
                # decision to make and needs to read it, not a traceback
                # through a script they did not write.
                print(f'{path}: {refusal}', file=sys.stderr)
                raise SystemExit(1) from None
            finally:
                memory.rollback()
                memory.close()
            print(json.dumps({'database': str(path), 'changes': counts}, ensure_ascii=False))
    if not args.apply:
        return
    args.backup_dir.mkdir(parents=True, exist_ok=False)
    for index, path in enumerate(args.databases):
        with sqlite3.connect(path) as source, sqlite3.connect(args.backup_dir / f'{index}-{path.name}') as backup:
            source.backup(backup)
    (args.backup_dir / 'manifest.json').write_text(json.dumps([str(p.resolve()) for p in args.databases], indent=2))
    for path in args.databases:
        with sqlite3.connect(path) as connection:
            connection.execute('BEGIN IMMEDIATE')
            migrate(connection)
    print('Migration complete; backups: ' + str(args.backup_dir))


if __name__ == '__main__':
    main()
