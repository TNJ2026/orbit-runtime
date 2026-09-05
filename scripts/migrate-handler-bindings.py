#!/usr/bin/env python3
"""Offline, backed-up migration from versioned to name/contract Handler refs.

Run without --apply first. Stop all Orbit writers before --apply. Historical
workflow version numbers are preserved. A hash collision aborts the migration.
"""
import argparse
import json
from pathlib import Path
import sqlite3

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


def migrate(connection):
    connection.row_factory = sqlite3.Row
    tables = {r[0] for r in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    counts = {}
    # Only this explicit offline migration may update published immutable rows.
    triggers = list(connection.execute("SELECT name,sql FROM sqlite_master WHERE type='trigger' AND tbl_name='workflow_versions'"))
    for row in triggers:
        connection.execute('DROP TRIGGER "' + row['name'].replace('"', '""') + '"')
    if 'workflow_versions' in tables:
        for row in list(connection.execute('SELECT rowid,* FROM workflow_versions')):
            graph = json.loads(row['canonical_ir_json'])
            changed = strip_versions(graph)
            source = source_without_versions(row['source_text'], row['source_format'])
            if changed or source != row['source_text']:
                ir = workflow_ir_from_primitive(graph)
                connection.execute('UPDATE workflow_versions SET canonical_ir_json=?,definition_hash=?,source_text=? WHERE rowid=?',
                                   (canonical_json(ir), definition_hash(ir).value, source, row['rowid']))
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
            counts = migrate(memory)
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
