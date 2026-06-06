// JcsRunner.java — cyberphone/json-canonicalization runner for AP2 open_mandate_hash v0.
//
// Uses Anders Rundgren's Java reference impl (the one cited in RFC 8785).
// The actual canonicalization is the unmodified JsonCanonicalizer class.
// This file adds only:
//   - a minimal JSON extractor to locate vector framing fields (mandate_body,
//     expected_open_mandate_hash, expectation, vector_id) within ap2-omh-v0.json
//   - SHA-256 + base64 wrappers around JsonCanonicalizer's byte output
//   - pair-invariant verification
//
// The minimal extractor uses brace-counting on the artefact file. Because the
// artefact shape is fixed (we publish it), this is safe; it is NOT a general
// JSON parser. Canonicalization correctness lives entirely in JsonCanonicalizer.
//
// Build:
//   git clone --depth 1 https://github.com/cyberphone/json-canonicalization.git
//   javac -d classes \
//         -sourcepath json-canonicalization/java/canonicalizer/src \
//         json-canonicalization/java/canonicalizer/src/org/webpki/jcs/JsonCanonicalizer.java \
//         JcsRunner.java
//   java -cp classes JcsRunner ap2-omh-v0.json

import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.security.MessageDigest;
import java.util.*;

import org.webpki.jcs.JsonCanonicalizer;

public class JcsRunner {

    static String toHex(byte[] b) {
        StringBuilder sb = new StringBuilder();
        for (byte x : b) sb.append(String.format("%02x", x & 0xff));
        return sb.toString();
    }

    // ── minimal artefact-specific JSON extractor ────────────────────────────
    // Finds occurrences of `"key"` at top of each vector object and returns
    // the next value: a JSON object/array (returned verbatim by brace count),
    // a JSON string (returned with quotes), or a bare literal.
    // ONLY used to slice ap2-omh-v0.json into per-vector chunks; canonicalization
    // is delegated to JsonCanonicalizer.
    static List<int[]> findVectorRanges(String src) {
        // Locate the top-level "vectors": [ … ] array and return the byte
        // ranges of each object inside it.
        int vIdx = src.indexOf("\"vectors\"");
        if (vIdx < 0) throw new IllegalArgumentException("no 'vectors' key");
        int br = src.indexOf('[', vIdx);
        List<int[]> ranges = new ArrayList<>();
        int depth = 0;
        boolean inStr = false, esc = false;
        int objStart = -1;
        for (int i = br + 1; i < src.length(); i++) {
            char c = src.charAt(i);
            if (esc) { esc = false; continue; }
            if (c == '\\') { esc = true; continue; }
            if (c == '"') { inStr = !inStr; continue; }
            if (inStr) continue;
            if (c == '{') {
                if (depth == 0) objStart = i;
                depth++;
            } else if (c == '}') {
                depth--;
                if (depth == 0) {
                    ranges.add(new int[]{objStart, i + 1});
                }
            } else if (c == ']' && depth == 0) {
                break;
            }
        }
        return ranges;
    }

    static String extractField(String vector, String key) {
        // Find the value following "key": within a single vector JSON object.
        String needle = "\"" + key + "\"";
        int idx = vector.indexOf(needle);
        if (idx < 0) return null;
        int colon = vector.indexOf(':', idx + needle.length());
        if (colon < 0) return null;
        int i = colon + 1;
        while (i < vector.length() && Character.isWhitespace(vector.charAt(i))) i++;
        if (i >= vector.length()) return null;
        char open = vector.charAt(i);

        if (open == '{' || open == '[') {
            char close = open == '{' ? '}' : ']';
            int depth = 0;
            boolean inStr = false, esc = false;
            int start = i;
            for (; i < vector.length(); i++) {
                char c = vector.charAt(i);
                if (esc) { esc = false; continue; }
                if (c == '\\') { esc = true; continue; }
                if (c == '"') { inStr = !inStr; continue; }
                if (inStr) continue;
                if (c == open) depth++;
                else if (c == close) {
                    depth--;
                    if (depth == 0) return vector.substring(start, i + 1);
                }
            }
        } else if (open == '"') {
            int start = i + 1;
            boolean esc = false;
            for (i = start; i < vector.length(); i++) {
                char c = vector.charAt(i);
                if (esc) { esc = false; continue; }
                if (c == '\\') { esc = true; continue; }
                if (c == '"') return vector.substring(start, i);
            }
        }
        return null;
    }

    public static void main(String[] args) throws Exception {
        if (args.length < 1) {
            System.err.println("usage: JcsRunner ap2-omh-v0.json");
            System.exit(2);
        }
        String src = new String(Files.readAllBytes(Paths.get(args[0])),
                                StandardCharsets.UTF_8);
        List<int[]> ranges = findVectorRanges(src);

        MessageDigest md = MessageDigest.getInstance("SHA-256");
        Map<String, String> computed = new LinkedHashMap<>();
        Map<String, String> expectations = new LinkedHashMap<>();
        int pass = 0, fail = 0;

        for (int[] r : ranges) {
            String vec = src.substring(r[0], r[1]);
            String vectorId = extractField(vec, "vector_id");
            String body = extractField(vec, "mandate_body");
            String expectedSha = extractField(vec, "expected_open_mandate_hash");
            String expectedB64 = extractField(vec, "expected_jcs_bytes_b64");
            String expectation = extractField(vec, "expectation");

            if (expectedSha != null && expectedSha.startsWith("sha256:")) {
                expectedSha = expectedSha.substring("sha256:".length());
            }
            expectations.put(vectorId, expectation == null ? "" : expectation);

            JsonCanonicalizer jc = new JsonCanonicalizer(body);
            byte[] jcsBytes = jc.getEncodedUTF8();
            md.reset();
            String sha = toHex(md.digest(jcsBytes));
            String b64 = Base64.getEncoder().encodeToString(jcsBytes);
            computed.put(vectorId, sha);

            boolean shaOk = expectedSha == null || expectedSha.equals(sha);
            boolean bytesOk = expectedB64 == null || expectedB64.equals(b64);
            boolean ok = shaOk && bytesOk;
            String mark = ok ? "OK  " : "FAIL";
            System.out.printf("  %s  %-34s  sha256:%s%n", mark, vectorId, sha);
            if (!ok) {
                if (!shaOk)   System.out.printf("        expected sha256:%s%n", expectedSha);
                if (!bytesOk) System.out.println("        bytes mismatch");
                fail++;
            } else {
                pass++;
            }
        }

        System.out.println("\n--- pair invariants ---");
        int pairFail = 0;
        for (Map.Entry<String, String> e : expectations.entrySet()) {
            String exp = e.getValue();
            if (exp.startsWith("same_hash_as:")) {
                String other = exp.substring("same_hash_as:".length());
                boolean ok = computed.get(e.getKey()).equals(computed.get(other));
                System.out.printf("  %s  %s == %s%n", ok ? "OK " : "FAIL", e.getKey(), other);
                if (!ok) pairFail++;
            } else if (exp.startsWith("different_hash_from:")) {
                String other = exp.substring("different_hash_from:".length());
                boolean ok = !computed.get(e.getKey()).equals(computed.get(other));
                System.out.printf("  %s  %s != %s%n", ok ? "OK " : "FAIL", e.getKey(), other);
                if (!ok) pairFail++;
            }
        }

        System.out.printf("%n%d/%d vectors match (cyberphone/json-canonicalization)%n",
            pass, pass + fail);
        System.out.printf("%d pair-invariant failures%n", pairFail);
        System.exit((fail == 0 && pairFail == 0) ? 0 : 1);
    }
}
