import { jsPDF } from 'jspdf'
import type { Invoice } from '../types/api'

export interface InvoiceMeta {
  patient?: string
  doctor?: string
  clinic?: string
}

/** Build and download a pharmacy invoice PDF (browser-side). */
export function downloadInvoicePdf(
  invoice: Invoice,
  meta: InvoiceMeta = {},
  filename = 'pharmacy-invoice.pdf',
) {
  const doc = new jsPDF()
  let y = 18

  doc.setFont('helvetica', 'bold')
  doc.setFontSize(16)
  doc.text('Pharmacy Invoice', 105, y, { align: 'center' })
  y += 12

  doc.setFont('helvetica', 'normal')
  doc.setFontSize(11)
  doc.text(`Patient: ${meta.patient || '—'}`, 14, y)
  y += 7
  doc.text(`Doctor: ${meta.doctor || '—'}`, 14, y)
  y += 7
  doc.text(`Clinic: ${meta.clinic || '—'}`, 14, y)
  y += 7
  doc.text(`Date: ${invoice.timestamp || new Date().toISOString()}`, 14, y)
  y += 12

  const colX = [14, 84, 114, 154]
  doc.setFont('helvetica', 'bold')
  doc.text('Medicine', colX[0], y)
  doc.text('Qty', colX[1], y)
  doc.text('Unit', colX[2], y)
  doc.text('Subtotal', colX[3], y)
  y += 6
  doc.setLineWidth(0.2)
  doc.line(14, y, 196, y)
  y += 8

  doc.setFont('helvetica', 'normal')
  for (const item of invoice.items) {
    if (y > 270) {
      doc.addPage()
      y = 20
    }
    doc.text(String(item.name).slice(0, 32), colX[0], y)
    doc.text(String(item.quantity), colX[1], y)
    doc.text(item.unit_price.toFixed(2), colX[2], y)
    doc.text(item.subtotal.toFixed(2), colX[3], y)
    y += 8
  }

  y += 4
  doc.line(14, y, 196, y)
  y += 10
  doc.setFont('helvetica', 'bold')
  doc.text(`Total: ${invoice.total.toFixed(2)}`, 14, y)

  doc.save(filename)
}
