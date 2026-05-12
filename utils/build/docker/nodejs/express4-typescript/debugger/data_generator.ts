interface DataGeneratorOptions {
  depth: number
  fields: number
  collectionSize: number
  stringLength: number
}

interface GeneratedData {
  deepObject: any
  manyFields: Record<string, number>
  largeCollection: number[]
  longString: string
}

export function dataGenerator ({ depth, fields, collectionSize, stringLength }: DataGeneratorOptions): GeneratedData {
  // Generate deeply nested object (tests maxReferenceDepth)
  const deepObject = depth > 0 ? createNestedObject(depth) : null

  // Generate object with many fields (tests maxFieldCount)
  const manyFields: Record<string, number> = {}
  for (let i = 0; i < fields; i++) {
    manyFields[`field${i}`] = i
  }

  // Generate large collection (tests maxCollectionSize)
  const largeCollection: number[] = []
  for (let i = 0; i < collectionSize; i++) {
    largeCollection.push(i)
  }

  // Generate long string (tests maxLength)
  const longString = stringLength > 0 ? 'A'.repeat(stringLength) : ''

  return {
    deepObject,
    manyFields,
    largeCollection,
    longString
  }
}

function createNestedObject (maxLevel: number, level = 1): any {
  if (level === maxLevel) return { level }
  return {
    level,
    nested: createNestedObject(maxLevel, level + 1)
  }
}
