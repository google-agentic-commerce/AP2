/**
 * Copyright 2025 Google LLC
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *     https://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */

/**
 * Finds and returns the value for the first occurrence of the key in the data parts.
 *
 * @param dataKey - The key to search for.
 * @param dataParts - The data parts to be searched (array of objects with data).
 * @returns The value for the first occurrence of the key, or null if not found.
 */
export const findDataPart = (
  dataKey: string,
  dataParts: Record<string, unknown>[]
): unknown => {
  for (const dataPart of dataParts) {
    if (dataKey in dataPart) {
      return dataPart[dataKey];
    }
  }
  return null;
};

/**
 * Finds and returns all values for the given key in the data parts.
 *
 * @param dataKey - The key to search for.
 * @param dataParts - The data parts to be searched (array of objects with data).
 * @returns An array of all values for the given key.
 */
export const findDataParts = (
  dataKey: string,
  dataParts: Record<string, unknown>[]
): unknown[] => {
  const dataPartsWithKey: unknown[] = [];
  for (const dataPart of dataParts) {
    if (dataKey in dataPart) {
      dataPartsWithKey.push(dataPart[dataKey]);
    }
  }
  return dataPartsWithKey;
};

/**
 * Converts the data part value for the given key to a canonical object using a Zod schema.
 * This is the TypeScript equivalent of Python's parse_canonical_object.
 *
 * @param dataKey - The key to search for.
 * @param dataParts - The data parts to be searched (array of objects with data).
 * @param schema - The Zod schema to validate and parse the data.
 * @returns The canonical object created from the data part value.
 * @throws Error if the data key is not found or validation fails.
 *
 * @example
 * const paymentMandate = parseCanonicalObject(
 *   "ap2.mandates.PaymentMandate",
 *   dataParts,
 *   paymentMandateSchema
 * );
 */
export const parseCanonicalObject = <T>(
  dataKey: string,
  dataParts: Record<string, unknown>[],
  schema: { parse: (data: unknown) => T }
): T => {
  const canonicalObjectData = findDataPart(dataKey, dataParts);
  if (!canonicalObjectData) {
    throw new Error(`${dataKey} not found in data parts.`);
  }
  return schema.parse(canonicalObjectData);
};
