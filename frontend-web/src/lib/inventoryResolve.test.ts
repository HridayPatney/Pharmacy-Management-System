import { describe, expect, it } from 'vitest'
import {
  medicineKey,
  mergeMedicineCatalogs,
  resolveSellLines,
} from './inventoryResolve'
import type { Medicine } from '../types/api'

const aspirin: Medicine = {
  id: 'med-1',
  name: 'Aspirin',
  dosage: '75mg',
  quantity: 20,
  price: 5.5,
  expiry_date: '2030-01-01',
}

describe('inventoryResolve', () => {
  it('normalizes names for lookup', () => {
    expect(medicineKey('  ASPIRIN  ')).toBe('aspirin')
    expect(medicineKey('Aspirin')).toBe('aspirin')
  })

  it('resolves sell lines from catalog even when only UI inventory has the row', () => {
    const lines = [{ name: 'aspirin', quantity: 2 }]
    const resolved = resolveSellLines(lines, [aspirin])
    expect(resolved).toEqual([{ id: 'med-1', name: 'Aspirin', quantity: 2 }])
  })

  it('prefers medicineId over name', () => {
    const other: Medicine = { ...aspirin, id: 'med-2', name: 'Ibuprofen' }
    const resolved = resolveSellLines(
      [{ name: 'wrong', quantity: 1, medicineId: 'med-1' }],
      [aspirin, other],
    )
    expect(resolved[0]).toEqual({ id: 'med-1', name: 'Aspirin', quantity: 1 })
  })

  it('merges catalogs by id', () => {
    const updated = { ...aspirin, quantity: 5 }
    expect(mergeMedicineCatalogs([aspirin], [updated])).toEqual([updated])
  })
})
