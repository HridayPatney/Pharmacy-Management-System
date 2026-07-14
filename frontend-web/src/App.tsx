import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import { AuthProvider } from './auth/AuthContext'
import { AppLayout } from './layout/AppLayout'
import { InventoryPage } from './pages/InventoryPage'
import { LoginPage } from './pages/LoginPage'
import { OcrInvoicePage } from './pages/OcrInvoicePage'

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route element={<AppLayout />}>
            <Route path="/inventory" element={<InventoryPage />} />
            <Route path="/ocr" element={<OcrInvoicePage />} />
          </Route>
          <Route path="*" element={<Navigate to="/inventory" replace />} />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  )
}
