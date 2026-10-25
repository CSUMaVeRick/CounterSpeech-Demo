const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const { webcrypto } = require('node:crypto');

const source = fs.readFileSync(path.join(__dirname, '../frontend/component.js'), 'utf8');
const script = '(' + source.replace('export default ', '') + ')';

for (const restored of [false, true]) {
  const root = {};
  const packets = [];
  const stored = new Map();
  const key = 'counter-speech-demo-v1';
  if (restored) stored.set(key, JSON.stringify({token:'a'.repeat(64), events:[{event_id:'existing-event'}], sequence:1}));
  const sandbox = {
    crypto: {getRandomValues: webcrypto.getRandomValues.bind(webcrypto)},
    localStorage: {getItem: key => stored.get(key) || null, setItem: (key, value) => stored.set(key, value)},
    document: {addEventListener() {}},
    setInterval() {return 0;},
    clearInterval() {},
  };
  // Simulate an HTTP browser: crypto exists but randomUUID does not.
  assert.equal(sandbox.crypto.randomUUID, undefined);
  const mount = vm.runInNewContext(script, sandbox);
  const data = {config:{conditions:[{id:'local_province'}]}, state:null, ack:[]};
  const send = (name, packet) => {assert.equal(name,'packet');packets.push(packet);};
  mount({parentElement:{querySelector:()=>root}, data, setStateValue:send});
  assert.equal(root.textContent, '正在连接实验环境…');
  assert.match(packets[0].token, /^[a-f0-9]{64}$/);
  assert.match(packets[0].attempt, /^[a-f0-9]{64}$/);
  assert.equal(packets[0].events.length, restored ? 1 : 0);
  if (restored) {
    assert.equal(packets[0].token,'a'.repeat(64));
    assert.equal(packets[0].events[0].event_id,'existing-event');
  }
  root.app.update(data,send);
  assert.equal(packets[1].token,packets[0].token);
  assert.notEqual(packets[1].attempt,packets[0].attempt);
}
console.log('HTTP startup and existing-session retry checks passed.');
