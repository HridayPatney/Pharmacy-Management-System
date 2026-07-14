import { describe, expect, it } from 'vitest'
import { canWriteInventory } from '../auth/AuthContext'

describe('canWriteInventory', () => {
  it('allows admin and pharmacist only', () => {
    expect(canWriteInventory('admin')).toBe(true)
    expect(canWriteInventory('pharmacist')).toBe(true)
    expect(canWriteInventory('cashier')).toBe(false)
    expect(canWriteInventory(undefined)).toBe(false)
  })
})
