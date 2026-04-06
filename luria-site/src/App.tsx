import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import Header from './components/layout/Header';
import HomePage from './pages/HomePage';
import AssetPage from './pages/AssetPage';
import FundPage from './pages/FundPage';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 2,
      refetchOnWindowFocus: false,
    },
  },
});

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <div className="min-h-screen bg-[#f7f9f8]">
          <Header />
          <Routes>
            <Route path="/" element={<HomePage />} />
            <Route path="/ativo/:ticker" element={<AssetPage />} />
            <Route path="/fundo/:cnpj" element={<FundPage />} />
          </Routes>
        </div>
      </BrowserRouter>
    </QueryClientProvider>
  );
}
