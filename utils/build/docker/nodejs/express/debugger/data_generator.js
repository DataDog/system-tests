'use strict'

module.exports = ({ depth, fields, collectionSize, stringLength }) => {
  // Generate deeply nested object (tests maxReferenceDepth)
  const deepObject = depth > 0 ? createNestedObject(depth) : null

  // Generate object with many fields (tests maxFieldCount)
  const manyFields = {}
  for (let i = 0; i < fields; i++) {
    manyFields[`field${i}`] = i
  }

  // Generate large collection (tests maxCollectionSize)
  const largeCollection = []
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

function createNestedObject (maxLevel, level = 1) {
  if (level === maxLevel) return { level }
  return {
    level,
    nested: createNestedObject(maxLevel, level + 1)
  }
}
