import { Navigate, Route, Routes } from 'react-router-dom';

import { Layout } from './components/Layout';
import { Carregando } from './components/ui';
import { useAuth } from './lib/auth';
import { Backtest } from './paginas/Backtest';
import { Entrar } from './paginas/Entrar';
import { Estudos } from './paginas/Estudos';
import { Grafico } from './paginas/Grafico';
import { Padroes } from './paginas/Padroes';
import { Painel } from './paginas/Painel';
import { Registrar } from './paginas/Registrar';
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
        <Route path="/" element={<Painel />} />
        <Route path="/grafico" element={<Grafico />} />
        <Route path="/sinais" element={<Sinais />} />
        <Route path="/estudos" element={<Estudos />} />
        <Route path="/padroes" element={<Padroes />} />
        <Route path="/backtest" element={<Backtest />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
