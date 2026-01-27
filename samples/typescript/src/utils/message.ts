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
