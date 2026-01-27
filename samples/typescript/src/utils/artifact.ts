/* eslint-disable @typescript-eslint/no-explicit-any */
// biome-ignore-all lint/suspicious/noExplicitAny: Utility functions work with dynamic data from A2A protocol
import type { Artifact } from "@a2a-js/sdk";

type ModelConstructor<T> = new (data: any) => T;

export function findCanonicalObjects<T>(
  artifacts: Artifact[],
  dataKey: string,
  ModelClass: ModelConstructor<T>
): T[] {
  const canonicalObjects: T[] = [];

  for (const artifact of artifacts) {
    for (const part of artifact.parts) {
      const partAny = part as any;
      // Check if part has a root with data property and contains the dataKey
      if (partAny.root?.data?.[dataKey]) {
        try {
          // Validate and instantiate the model
          const validatedObject = new ModelClass(partAny.root.data[dataKey]);
          canonicalObjects.push(validatedObject);
        } catch (error) {
          // Skip invalid objects or log error as needed
          console.warn(`Failed to validate object for key ${dataKey}:`, error);
        }
      }
    }
  }

  return canonicalObjects;
}

export const getFirstDataPart = (
  artifacts: Artifact[]
): Record<string, any> => {
  for (const artifact of artifacts) {
    for (const part of artifact.parts) {
      if (part.kind === "data") {
        return (part as any).data;
      }
    }
  }
  return {};
};
