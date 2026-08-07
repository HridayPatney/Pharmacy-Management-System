import type { Medicine } from '../types/api'

/** Normalize medicine names for case/whitespace-insensitive matching. */
export function medicineKey(name: string): string {
  return name.normalize('NFKC').trim().toLowerCase().replace(/\s+/g, ' ')
}

export function indexMedicines(meds: Medicine[]) {
  const byId = new Map<string, Medicine>()
  const byName = new Map<string, Medicine>()
  for (const m of meds) {
    byId.set(m.id, m)
    byName.set(medicineKey(m.name), m)
  }
  return { byId, byName }
}

export function mergeMedicineCatalogs(...lists: Medicine[][]) {
  const byId = new Map<string, Medicine>()
  for (const list of lists) {
    for (const m of list) byId.set(m.id, m)
  }
  return [...byId.values()]
}

export function resolveSellLines(
  lines: { name: string; quantity: number; medicineId?: string }[],
  catalog: Medicine[],
) {
  const { byId, byName } = indexMedicines(catalog)
  return lines
    .map((l) => {
      const trimmed = l.name.normalize('NFKC').trim().replace(/\s+/g, ' ')
      const stock =
        (l.medicineId ? byId.get(l.medicineId) : undefined) ??
        byName.get(medicineKey(trimmed))
      return {
        id: stock?.id,
        name: stock?.name ?? trimmed,
        quantity: l.quantity,
      }
    })
    .filter((l) => l.name && l.quantity > 0)
}
