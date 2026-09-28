const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');
const { webcrypto } = require('node:crypto');

test('processes two PDFs concurrently and generates Excel only after all finish', async () => {
    const html = fs.readFileSync(path.join(__dirname, '..', 'templates', 'index.html'), 'utf8');
    const script = html.match(/<script>([\s\S]*?)<\/script>/)[1];
    const elements = new Map();
    const element = id => {
        if (!elements.has(id)) {
            elements.set(id, {
                disabled: true, style: {}, classList: { toggle() {} },
                replaceChildren() {}, appendChild() {}, addEventListener() {},
            });
        }
        return elements.get(id);
    };
    const pending = [];
    let active = 0;
    let maxActive = 0;
    let completed = false;
    const context = vm.createContext({
        document: {
            documentElement: {}, getElementById: element,
            querySelectorAll: () => [],
            createElement: () => ({setAttribute() {}, addEventListener() {}, append() {}, remove() {}}),
        },
        localStorage: { getItem: () => 'en' },
        window: { setTimeout: () => 1, clearTimeout() {} },
        crypto: webcrypto,
        FormData,
        AbortController,
        performance,
        fetch: (url, options) => {
            if (url === '/process/cancel') return Promise.resolve({ok: true});
            if (url === '/process/complete') {
                assert.equal(active, 0);
                assert.equal(pending.length, 3);
                completed = true;
                return Promise.resolve({
                    ok: true, status: 200,
                    text: async () => JSON.stringify({ ahu_count: 3, ahu_list: ['1', '2', '3'],
                        filename: 'result.xlsx', download_url: '/download/result.xlsx' }),
                });
            }
            assert.equal(url, '/process');
            active++;
            maxActive = Math.max(maxActive, active);
            return new Promise(resolve => pending.push({
                index: Number(options.body.get('batch_index')),
                finish() {
                    active--;
                    resolve({ok: true, status: 200, text: async () => '{"success":true}'});
                },
            }));
        },
    });
    vm.runInContext(script, context);
    vm.runInContext(`selectedType = 'airborne_particle'; uploadedFiles = [
        {name: 'AHU-1.pdf', size: 100}, {name: 'AHU-2.pdf', size: 100},
        {name: 'AHU-3.pdf', size: 100}
    ];`, context);

    const processing = vm.runInContext('processFiles()', context);
    await new Promise(resolve => setImmediate(resolve));
    assert.equal(pending.length, 2, element('statusMsg').textContent);
    pending[1].finish();
    await new Promise(resolve => setImmediate(resolve));
    assert.equal(pending.length, 3);
    assert.equal(completed, false);
    pending[0].finish();
    pending[2].finish();
    await processing;

    assert.equal(maxActive, 2);
    assert.equal(completed, true);
    assert.match(element('statusMsg').innerHTML, /3 AHU/);
});
