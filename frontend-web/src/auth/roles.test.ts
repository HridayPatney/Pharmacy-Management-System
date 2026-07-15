import { describe, expect, it } from 'vitest'
import { canManageStaff, canWriteInventory } from '../auth/AuthContext'

describe('canWriteInventory', () => {
  it('allows admin and pharmacist only', () => {
    expect(canWriteInventory('admin')).toBe(true)
    expect(canWriteInventory('pharmacist')).toBe(true)
    expect(canWriteInventory('cashier')).toBe(false)
    expect(canWriteInventory(undefined)).toBe(false)
  })
})

describe('canManageStaff', () => {
  it('allows admin only', () => {
    expect(canManageStaff('admin')).toBe(true)
    expect(canManageStaff('pharmacist')).toBe(false)
    expect(canManageStaff('cashier')).toBe(false)
    expect(canManageStaff(undefined)).toBe(false)
  })
})
