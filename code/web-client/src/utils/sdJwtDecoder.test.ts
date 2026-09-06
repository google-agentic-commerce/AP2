import {describe, expect, it} from 'vitest';
import {decodeSdJwt, decodeSdJwtSync} from './sdJwtDecoder';

// A genuine 2-hop dSD-JWT delegation chain (draft-gco-oauth-delegate-sd-jwt-00
// SS6) minted by the AP2 Python reference SDK: an OpenCheckoutMandate root
// hop delegating to an agent key, then a CheckoutMandate KB-SD-JWT hop
// presented to "merchant". Hop 0 carries 1 disclosure, hop 1 carries 2.
const REAL_TWO_HOP_CHAIN =
  // cspell:disable-next-line
  'eyJhbGciOiAiRVMyNTYiLCAidHlwIjogImV4YW1wbGUrc2Qtand0In0.eyJkZWxlZ2F0ZV9wYXlsb2FkIjogW3siLi4uIjogInJ3TFVNZ1hXM3NNTjZ5bjVnM25qb0JIMVMzUFY0ajluRnhCcHFhMDJwNG8ifV0sICJfc2RfYWxnIjogInNoYS0yNTYifQ.Pj4SJi9BelCFns_TuxOTH2b-7psu2DA4SISLmqcikSn1GiqhqAjVYxXK_hhUBwp4ofslSGauCrBiKn_VXSCwBg~WyJKUU5ES2xEZGxKRUgwYlY5RUFweDRBIiwgeyJ2Y3QiOiAibWFuZGF0ZS5jaGVja291dC5vcGVuLjEiLCAiY29uc3RyYWludHMiOiBbXSwgImNuZiI6IHsiandrIjogeyJrdHkiOiAiRUMiLCAiY3J2IjogIlAtMjU2IiwgIngiOiAibWtYNUJNNW1LbmhTMzZjMHVLZWNHNW16M0VvU1VyYnA3bjF5bmdNdWJBTSIsICJ5IjogIlRCRkRfdkRTdWdBZmluMVdIZnlBUHNndmhSQjVKNFQyTWhtVVZ4cFJRN1kiLCAiYWxnIjogIkVTMjU2In19fV0~~eyJhbGciOiAiRVMyNTYiLCAidHlwIjogImtiK3NkLWp3dCJ9.eyJkZWxlZ2F0ZV9wYXlsb2FkIjogW3siLi4uIjogIjU2UmpJZk8weVBGRm9mVHhMZVBUejNJX3pKaFM1bjJQY3ZqWTg1Nk9vbFEifV0sICJpYXQiOiAxNzg4NTY4Nzg4LCAiYXVkIjogIm1lcmNoYW50IiwgIm5vbmNlIjogIm1lcmNoYW50LW5vbmNlIiwgInNkX2hhc2giOiAiVFVTUWlmd2U1OFpxRjJSVWtHLVVwZTh1TjQtSkxUZU5ELXRrbmpBdmtRTSIsICJfc2RfYWxnIjogInNoYS0yNTYifQ.a7LvlGynBP_zAVbA_HZjqWSALfiH_HuVuP9A8_ApgxyKGx1PXTx4_U4-5PWkLC0ZRXFr_tKIQAhoBUXdCIISEg~WyJnbGVTN0l5bG9NREJsbExxZ1lsRUxBIiwgeyJfc2QiOiBbIjVoR0ctNVhOdmVuQTFyaURLczRIazJtTmtWZElabGZJU2dObjByV0d3LU0iXSwgInZjdCI6ICJtYW5kYXRlLmNoZWNrb3V0LjEiLCAiY2hlY2tvdXRfaGFzaCI6ICJoYXNoIn1d~WyJQUlR5em5CZ05PNWE5UnR4T1BEa1lBIiwgImNoZWNrb3V0X2p3dCIsICJoZHIuYm9keS5zaWciXQ~';

// A plain single-hop SD-JWT issuance (no chain), used to prove the fix
// doesn't change the existing single-token behavior at all.
const SINGLE_HOP_TOKEN =
  // cspell:disable-next-line
  'eyJhbGciOiAiRVMyNTYiLCAidHlwIjogImV4YW1wbGUrc2Qtand0In0.eyJfc2QiOiBbXX0.VStKGOA5TdLsrjahM4dRfDrbsy7BmrUNGw3jaBuxZnHYvmS2EnQ-ib7zSCUVBGGbcyORDFCMd_F6gr8CM9N3WQ~';

describe('decodeSdJwt / decodeSdJwtSync', () => {
  for (const decode of [decodeSdJwt, decodeSdJwtSync]) {
    describe(decode.name, () => {
      it('decodes a plain single-hop token exactly as before (no `hops`)', async () => {
        const decoded = await decode(SINGLE_HOP_TOKEN);
        expect(decoded.hops).toBeUndefined();
        expect(decoded.issuerJwt.payload._sd).toEqual([]);
        expect(decoded.disclosures).toEqual([]);
        expect(decoded.kbJwt).toBeUndefined();
      });

      it('decodes every hop of a real 2-hop delegation chain, not just the first', async () => {
        const decoded = await decode(REAL_TWO_HOP_CHAIN);

        expect(decoded.hops).toHaveLength(2);
        const [hop0, hop1] = decoded.hops!;

        // Hop 0: the root Open Checkout Mandate, 1 disclosure.
        expect(hop0.issuerJwt.payload.delegate_payload).toBeDefined();
        expect(hop0.disclosures).toHaveLength(1);
        expect(hop0.kbJwt).toBeUndefined();

        // Hop 1: the terminal KB-SD-JWT, 2 disclosures. Under the old
        // single-`~`-split logic these were silently dropped or
        // credited to hop 0 instead.
        expect(hop1.issuerJwt.header.typ).toBe('kb+sd-jwt');
        expect(hop1.issuerJwt.payload.aud).toBe('merchant');
        expect(hop1.disclosures).toHaveLength(2);
        expect(hop1.kbJwt).toBeUndefined();

        // Top-level fields describe hop 0, for backward compatibility with
        // existing single-hop callers.
        expect(decoded.issuerJwt).toEqual(hop0.issuerJwt);
        expect(decoded.disclosures).toEqual(hop0.disclosures);
      });
    });
  }
});
