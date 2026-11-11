import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readdirSync, readFileSync } from 'node:fs';
import path from 'node:path';
import ts from 'typescript';

const root = path.resolve('frontend/ssui_components/src/components');
function files(dir) {
    return readdirSync(dir, { withFileTypes: true }).flatMap(entry =>
        entry.isDirectory() ? files(path.join(dir, entry.name)) : [path.join(dir, entry.name)]);
}

test('every registered shared editor has an explicit Storybook entry', () => {
    const sources = files(root).filter(file => file.endsWith('.tsx'));
    const stories = sources.filter(file => file.includes('.stories.')).map(file => readFileSync(file, 'utf8')).join('\n');
    const names = new Set();
    for (const file of sources.filter(file => !file.includes('.stories.'))) {
        const ast = ts.createSourceFile(file, readFileSync(file, 'utf8'), ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX);
        function visit(node) {
            if (ts.isObjectLiteralExpression(node)) {
                const fields = new Map(node.properties.filter(ts.isPropertyAssignment).map(property =>
                    [property.name.getText(ast).replace(/['"]/g, ''), property.initializer]));
                const name = fields.get('name');
                // Includes both literal registrations and the local-model spec factory.
                if (name && ts.isStringLiteral(name) && fields.has('type') && (fields.has('port') || fields.has('fields'))) names.add(name.text);
            }
            ts.forEachChild(node, visit);
        }
        visit(ast);
    }
    assert.ok(names.size > 40, 'component inventory must not silently become empty');
    const missing = [...names].filter(name => !stories.includes(`"name": "${name}"`) && !stories.includes(`name: '${name}'`));
    assert.deepEqual(missing, [], `Add explicit registered-editor stories for: ${missing.join(', ')}`);
});
