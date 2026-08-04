#!/usr/bin/env node
/**
 * runner_node.js — canonicalize@3.0.0 (Erdtman) runner for AP2 open_mandate_hash v0.
 *
 * Reads vectors-v0.json, recomputes JCS + SHA-256 for each vector, and verifies
 * recomputed hashes match `expected_open_mandate_hash` and pair expectations.
 * For vectors carrying `jws_compact`, also verifies the decoded JWS payload
 * re-canonicalizes to the same hash (envelope invariance; signatures are not
 * verified).
 *
 * Usage:
 *   npm install canonicalize@3.0.0
 *   node --input-type=module runner_node.js vectors-v0.json
 *
 * Or save next to a package.json with `{ "type": "module" }`.
 */
import fs from 'fs';
import crypto from 'crypto';
import canonicalize from 'canonicalize';

function hashVector(body) {
  const jcs = canonicalize(body);
  const jcsBytes = Buffer.from(jcs, 'utf8');
  return {
    bytes_b64: jcsBytes.toString('base64'),
    sha256: crypto.createHash('sha256').update(jcsBytes).digest('hex'),
  };
}

function jwsPayloadHash(jwsCompact) {
  // sha256 hex of the canonicalized claims parsed from the JWS payload.
  // Envelope invariance check only; signatures are not verified.
  const payload = Buffer.from(jwsCompact.split('.')[1], 'base64url');
  const claims = JSON.parse(payload.toString('utf8'));
  return hashVector(claims).sha256;
}

function main() {
  if (process.argv.length < 3) {
    console.error('usage: node runner_node.js vectors-v0.json');
    process.exit(2);
  }
  const data = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
  const vectors = data.vectors;
  const computed = {};
  let pass = 0, fail = 0;

  for (const v of vectors) {
    const { bytes_b64, sha256 } = hashVector(v.mandate_body);
    computed[v.vector_id] = sha256;
    const expectedSha = v.expected_open_mandate_hash.replace(/^sha256:/, '');
    const bytesOk = bytes_b64 === v.expected_jcs_bytes_b64;
    const shaOk = sha256 === expectedSha;
    const jwsOk = v.jws_compact ? jwsPayloadHash(v.jws_compact) === sha256 : true;
    const ok = bytesOk && shaOk && jwsOk;
    const mark = ok ? 'OK ' : 'FAIL';
    console.log(`  ${mark}  ${v.vector_id.padEnd(34)}  sha256:${sha256}`);
    if (!ok) {
      if (!bytesOk) console.log(`        bytes mismatch`);
      if (!shaOk) console.log(`        expected sha256:${expectedSha}`);
      if (!jwsOk) console.log(`        jws payload hash mismatch (envelope invariance broken)`);
    }
    if (ok) pass++; else fail++;
  }

  console.log('\n--- pair invariants ---');
  let pairFail = 0;
  for (const v of vectors) {
    const exp = v.expectation || '';
    if (exp.startsWith('same_hash_as:')) {
      const other = exp.split(':')[1];
      const ok = computed[v.vector_id] === computed[other];
      console.log(`  ${ok ? 'OK ' : 'FAIL'}  ${v.vector_id} == ${other}`);
      if (!ok) pairFail++;
    } else if (exp.startsWith('different_hash_from:')) {
      const other = exp.split(':')[1];
      const ok = computed[v.vector_id] !== computed[other];
      console.log(`  ${ok ? 'OK ' : 'FAIL'}  ${v.vector_id} != ${other}`);
      if (!ok) pairFail++;
    }
  }

  console.log(`\n${pass}/${pass + fail} vectors match (canonicalize@3.0.0)`);
  console.log(`${pairFail} pair-invariant failures`);
  process.exit(fail === 0 && pairFail === 0 ? 0 : 1);
}

main();
