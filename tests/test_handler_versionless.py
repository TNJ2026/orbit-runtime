import copy
import importlib.util
import json
from pathlib import Path
import sqlite3
import unittest

from orbit.workflow.application.workflows import load_catalogs
from orbit.workflow.dsl import compile_source, DiagnosticError
from orbit.workflow.domain.serialization import canonical_json, definition_hash, to_primitive
from orbit.workflow.domain.ir_schema import workflow_ir_from_primitive


class VersionlessHandlerTests(unittest.TestCase):
    def setUp(self):
        root = Path(__file__).parent / 'fixtures/workflow_dsl/v1'
        self.document = json.loads((root / 'linear.json').read_text())
        self.catalogs = load_catalogs(root / 'catalog.json')

    def compile(self, document):
        return compile_source(json.dumps(document), self.catalogs.handlers, self.catalogs.schemas, source_format='json')

    def test_handler_version_is_rejected_and_contract_is_persisted(self):
        compiled = self.compile(self.document)
        handler = next(n.handler for n in compiled.ir.nodes if n.handler)
        self.assertEqual({'name', 'manifest_fingerprint'}, set(to_primitive(handler)))
        document = copy.deepcopy(self.document)
        next(n['handler'] for n in document['nodes'] if n.get('handler'))['version'] = '1.0.0'
        with self.assertRaises(DiagnosticError):
            self.compile(document)

    def test_build_version_does_not_change_definition_hash(self):
        from dataclasses import replace
        from orbit.workflow.catalogs import InMemoryHandlerCatalog
        first = self.compile(self.document)
        manifest = self.catalogs.handlers.resolve("collect")
        newer = InMemoryHandlerCatalog([replace(manifest, version="9.0.0")])
        second = compile_source(json.dumps(self.document), newer, self.catalogs.schemas, source_format="json")
        self.assertEqual(first.definition_hash, second.definition_hash)
        self.assertEqual(first.ir, second.ir)

    def test_offline_migration_rehashes_and_restores_immutability(self):
        spec = importlib.util.spec_from_file_location('binding_migration', Path(__file__).parents[1] / 'scripts/migrate-handler-bindings.py')
        migration = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(migration)
        graph = to_primitive(self.compile(self.document).ir)
        next(n['handler'] for n in graph['nodes'] if n.get('handler'))['version'] = '1.0.0'
        source = copy.deepcopy(self.document)
        next(n['handler'] for n in source['nodes'] if n.get('handler'))['version'] = '1.0.0'
        connection = sqlite3.connect(':memory:')
        self.addCleanup(connection.close)
        connection.executescript('''CREATE TABLE workflow_versions(canonical_ir_json TEXT, definition_hash TEXT, source_text TEXT, source_format TEXT);
        CREATE TRIGGER immutable BEFORE UPDATE ON workflow_versions BEGIN SELECT RAISE(ABORT,'immutable'); END;''')
        connection.execute('INSERT INTO workflow_versions VALUES(?,?,?,?)', (json.dumps(graph), 'old', json.dumps(source), 'json'))
        self.assertEqual({'workflow_versions': 1}, migration.migrate(connection))
        row = connection.execute('SELECT * FROM workflow_versions').fetchone()
        ir = workflow_ir_from_primitive(json.loads(row['canonical_ir_json']))
        self.assertEqual(definition_hash(ir).value, row['definition_hash'])
        self.compile(json.loads(row['source_text']))
        self.assertEqual({}, migration.migrate(connection))
        with self.assertRaises(sqlite3.IntegrityError):
            connection.execute("UPDATE workflow_versions SET definition_hash='bad'")
