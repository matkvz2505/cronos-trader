import { Navigate, Route, Routes } from 'react-router-dom';

import { Layout } from './components/Layout';
import { Carregando } from './components/ui';
import { useAuth } from './lib/auth';
import { Alertas } from './paginas/Alertas';
import { Conhecimento } from './paginas/Conhecimento';
import { Diario } from './paginas/Diario';
import { Entrar } from './paginas/Entrar';
import { Grafico } from './paginas/Grafico';
import { Mesa } from './paginas/Mesa';
import { Registrar } from './paginas/Registrar';
import { Sala } from './paginas/Sala';
import { Sinais } from './paginas/Sinais';

export function App() {
  const { usuario, carregando } = useAuth();

  // Espera a revalidação da sessão antes de decidir a rota. Sem isso, um reload numa
  // página interna piscaria o login por um instante antes de voltar.
  if (carregando) return <Carregando texto="verificando sessão…" />;

  if (!usuario) {
    return (
      <Routes>
        <Route path="/entrar" element={<Entrar />} />
        <Route path="/registrar" element={<Registrar />} />
        <Route path="*" element={<Navigate to="/entrar" replace />} />
      </Routes>
    );
  }

  return (
    <Routes>
      <Route element={<Layout />}>
        <Route path="/" element={<Mesa />} />
        {/* Uma sala por ativo. São mercados diferentes e merecem telas diferentes. */}
        <Route path="/sala/:ativo" element={<Sala />} />
        <Route path="/alertas" element={<Alertas />} />
        <Route path="/grafico" element={<Grafico />} />
        <Route path="/diario" element={<Diario />} />
        <Route path="/historico" element={<Sinais />} />
        <Route path="/conhecimento" element={<Conhecimento />} />

        {/* Rotas antigas — redirecionam em vez de dar 404 para quem tem link salvo. */}
        <Route path="/sinais" element={<Navigate to="/historico" replace />} />
        <Route path="/padroes" element={<Navigate to="/conhecimento" replace />} />
        <Route path="/estudos" element={<Navigate to="/conhecimento" replace />} />
        <Route path="/backtest" element={<Navigate to="/conhecimento" replace />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
