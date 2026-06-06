/**
 * JCS runner for AP2 open_mandate_hash v0 conformance vectors.
 *
 * <p>Uses Anders Rundgren's Java reference implementation
 * (cyberphone/json-canonicalization), cited in RFC 8785.
 *
 * <p>Build:
 *
 * <pre>
 *   git clone --depth 1 \
 *     https://github.com/cyberphone/json-canonicalization.git
 *   javac -d classes \
 *     -sourcepath \
 *     json-canonicalization/java/canonicalizer/src \
 *     json-canonicalization/java/canonicalizer/src/org/webpki/jcs/\
 *     JsonCanonicalizer.java \
 *     JcsRunner.java
 *   java -cp classes JcsRunner vectors-v0.json
 * </pre>
 */

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Paths;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.ArrayList;
import java.util.Base64;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

import org.webpki.jcs.JsonCanonicalizer;

/** JCS runner for AP2 open_mandate_hash v0 conformance vectors. */
public final class JcsRunner {

  private static final int BYTE_MASK = 0xff;

  private JcsRunner() {}

  private static String toHex(final byte[] b) {
    final StringBuilder sb = new StringBuilder();
    for (final byte x : b) {
      sb.append(String.format("%02x", x & BYTE_MASK));
    }
    return sb.toString();
  }

  private static List<int[]> findVectorRanges(final String src) {
    final int vIdx = src.indexOf("\"vectors\"");
    if (vIdx < 0) {
      throw new IllegalArgumentException("no 'vectors' key");
    }
    final int br = src.indexOf('[', vIdx);
    final List<int[]> ranges = new ArrayList<>();
    int depth = 0;
    boolean inStr = false;
    boolean esc = false;
    int objStart = -1;
    for (int i = br + 1; i < src.length(); i++) {
      final char c = src.charAt(i);
      if (esc) {
        esc = false;
        continue;
      }
      if (c == '\\') {
        esc = true;
        continue;
      }
      if (c == '"') {
        inStr = !inStr;
        continue;
      }
      if (inStr) {
        continue;
      }
      if (c == '{') {
        if (depth == 0) {
          objStart = i;
        }
        depth++;
      } else if (c == '}') {
        depth--;
        if (depth == 0) {
          ranges.add(new int[] {objStart, i + 1});
        }
      } else if (c == ']' && depth == 0) {
        break;
      }
    }
    return ranges;
  }

  private static String extractField(final String vector, final String key) {
    final String needle = "\"" + key + "\"";
    final int idx = vector.indexOf(needle);
    if (idx < 0) {
      return null;
    }
    final int colon = vector.indexOf(':', idx + needle.length());
    if (colon < 0) {
      return null;
    }
    int i = colon + 1;
    while (i < vector.length()
        && Character.isWhitespace(vector.charAt(i))) {
      i++;
    }
    if (i >= vector.length()) {
      return null;
    }
    final char open = vector.charAt(i);
    if (open == '{' || open == '[') {
      return extractObject(vector, i, open);
    } else if (open == '"') {
      return extractString(vector, i + 1);
    }
    return null;
  }

  private static String extractObject(
      final String vector, final int start, final char open) {
    final char close = open == '{' ? '}' : ']';
    int depth = 0;
    boolean inStr = false;
    boolean esc = false;
    for (int i = start; i < vector.length(); i++) {
      final char c = vector.charAt(i);
      if (esc) {
        esc = false;
        continue;
      }
      if (c == '\\') {
        esc = true;
        continue;
      }
      if (c == '"') {
        inStr = !inStr;
        continue;
      }
      if (inStr) {
        continue;
      }
      if (c == open) {
        depth++;
      } else if (c == close) {
        depth--;
        if (depth == 0) {
          return vector.substring(start, i + 1);
        }
      }
    }
    return null;
  }

  private static String extractString(
      final String vector, final int start) {
    boolean esc = false;
    for (int i = start; i < vector.length(); i++) {
      final char c = vector.charAt(i);
      if (esc) {
        esc = false;
        continue;
      }
      if (c == '\\') {
        esc = true;
        continue;
      }
      if (c == '"') {
        return vector.substring(start, i);
      }
    }
    return null;
  }

  /**
   * Entry point.
   *
   * @param args command-line arguments; args[0] is the vector file path
   * @throws IOException on file read error
   * @throws NoSuchAlgorithmException if SHA-256 is unavailable
   */
  public static void main(final String[] args)
      throws IOException, NoSuchAlgorithmException {
    if (args.length < 1) {
      System.err.println("usage: JcsRunner vectors-v0.json");
      System.exit(2);
    }
    final String src = new String(
        Files.readAllBytes(Paths.get(args[0])), StandardCharsets.UTF_8);
    final List<int[]> ranges = findVectorRanges(src);
    final MessageDigest md = MessageDigest.getInstance("SHA-256");
    final Map<String, String> computed = new LinkedHashMap<>();
    final Map<String, String> expectations = new LinkedHashMap<>();
    int pass = 0;
    int fail = 0;

    for (final int[] r : ranges) {
      final String vec = src.substring(r[0], r[1]);
      final String vectorId = extractField(vec, "vector_id");
      final String body = extractField(vec, "mandate_body");
      String expectedSha = extractField(vec, "expected_open_mandate_hash");
      final String expectedB64 =
          extractField(vec, "expected_jcs_bytes_b64");
      final String expectation = extractField(vec, "expectation");

      if (expectedSha != null && expectedSha.startsWith("sha256:")) {
        expectedSha = expectedSha.substring("sha256:".length());
      }
      expectations.put(vectorId, expectation == null ? "" : expectation);

      final JsonCanonicalizer jc = new JsonCanonicalizer(body);
      final byte[] jcsBytes = jc.getEncodedUTF8();
      md.reset();
      final String sha = toHex(md.digest(jcsBytes));
      final String b64 = Base64.getEncoder().encodeToString(jcsBytes);
      computed.put(vectorId, sha);

      final boolean shaOk =
          expectedSha == null || expectedSha.equals(sha);
      final boolean bytesOk =
          expectedB64 == null || expectedB64.equals(b64);
      final boolean ok = shaOk && bytesOk;
      final String mark = ok ? "OK  " : "FAIL";
      System.out.printf(
          "  %s  %-34s  sha256:%s%n", mark, vectorId, sha);
      if (!ok) {
        if (!shaOk) {
          System.out.printf(
              "        expected sha256:%s%n", expectedSha);
        }
        if (!bytesOk) {
          System.out.println("        bytes mismatch");
        }
        fail++;
      } else {
        pass++;
      }
    }

    System.out.println("\n--- pair invariants ---");
    int pairFail = 0;
    for (final Map.Entry<String, String> entry
        : expectations.entrySet()) {
      final String exp = entry.getValue();
      if (exp.startsWith("same_hash_as:")) {
        final String other =
            exp.substring("same_hash_as:".length());
        final boolean ok =
            computed.get(entry.getKey()).equals(computed.get(other));
        System.out.printf(
            "  %s  %s == %s%n",
            ok ? "OK " : "FAIL",
            entry.getKey(),
            other);
        if (!ok) {
          pairFail++;
        }
      } else if (exp.startsWith("different_hash_from:")) {
        final String other =
            exp.substring("different_hash_from:".length());
        final boolean ok =
            !computed.get(entry.getKey()).equals(computed.get(other));
        System.out.printf(
            "  %s  %s != %s%n",
            ok ? "OK " : "FAIL",
            entry.getKey(),
            other);
        if (!ok) {
          pairFail++;
        }
      }
    }

    System.out.printf(
        "%n%d/%d vectors match (cyberphone/json-canonicalization)%n",
        pass,
        pass + fail);
    System.out.printf("%d pair-invariant failures%n", pairFail);
    System.exit((fail == 0 && pairFail == 0) ? 0 : 1);
  }
}
