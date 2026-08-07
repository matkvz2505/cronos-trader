import { NavLink, Outlet, useNavigate } from 'react-router-dom';

import { useAuth } from '../lib/auth';
import { reais } from '../lib/formato';
import { useSinaisAoVivo } from '../lib/useSinaisAoVivo';

/**
 * A ordem segue o fluxo de trabalho, não a arquitetura: o que está aberto agora, o
 * gráfico para conferir, o histórico para revisar, e só depois as ferramentas de estudo.
 */
const NAVEGACAO = [
  { para: '/', rotulo: 'Painel', fim: true },
  { para: '/grafico', rotulo: 'Gráfico' },
  { para: '/sinais', rotulo: 'Sinais' },
  { para: '/estudos', rotulo: 'Estudos' },
  { para: '/padroes', rotulo: 'Padrões' },
  { para: '/backtest', rotulo: 'Backtest' },
];

export function Layout() {
  const { usuario, sair } = useAuth();
  const { estado } = useSinaisAoVivo();
  const navegar = useNavigate();

  async function aoSair() {
    await sair();
    navegar('/entrar');
  }

  return (
    <div className="min-h-screen">
      <header className="sticky top-0 z-20 border-b border-borda bg-fundo/95 backdrop-blur">
        <div className="mx-auto flex h-14 max-w-[1600px] items-center gap-6 px-4">
          <div className="flex items-center gap-2">
            <span className="text-lg">📈</span>
            <span className="font-semibold tracking-tight">
              Cronos <span className="text-marca">Trader</span>
            </span>
            <span className="ml-1 rounded bg-superficie-alta px-1.5 py-0.5 text-[10px] font-medium text-texto-fraco">
              WIN · WDO
            </span>
          </div>

          <nav className="flex items-center gap-1">
            {NAVEGACAO.map((item) => (
              <NavLink
                key={item.para}
                to={item.para}
                end={item.fim}
                className={({ isActive }) =>
                  `rounded-lg px-3 py-1.5 text-sm transition-colors ${
                    isActive
                      ? 'bg-superficie-alta text-texto'
                      : 'text-texto-suave hover:bg-superficie hover:text-texto'
                  }`
                }
              >
                {item.rotulo}
              </NavLink>
            ))}
          </nav>

          <div className="ml-auto flex items-center gap-4">
            <IndicadorConexao estado={estado} />
            <div className="hidden text-right sm:block">
              <p className="text-xs text-texto-suave">{usuario?.nome}</p>
              <p className="numerico text-xs text-texto-fraco">{reais(usuario?.capital ?? 0)}</p>
            </div>
            <button
              onClick={aoSair}
              className="rounded-lg border border-borda px-3 py-1.5 text-sm text-texto-suave transition-colors hover:border-borda-forte hover:text-texto"
            >
              Sair
            </button>
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-[1600px] px-4 py-6">
        <Outlet />
      </main>

      <footer className="mx-auto max-w-[1600px] px-4 pb-8">
        <p className="text-xs leading-relaxed text-texto-fraco">
          Ferramenta de <strong>apoio à decisão</strong> — não é recomendação de investimento.
          Mini-índice e mini-dólar são contratos alavancados: a perda pode superar o capital
          depositado. Nenhuma taxa de acerto histórica garante resultado futuro.
        </p>
      </footer>
    </div>
  );
}

function IndicadorConexao({ estado }: { estado: 'conectando' | 'conectado' | 'desconectado' }) {
  const config = {
    conectado: { cor: 'bg-alta', texto: 'ao vivo' },
    conectando: { cor: 'bg-aviso animate-pulse', texto: 'conectando' },
    desconectado: { cor: 'bg-baixa', texto: 'offline' },
  }[estado];

  return (
    <span className="flex items-center gap-1.5 text-xs text-texto-fraco" title="Conexão de sinais ao vivo">
      <span className={`h-1.5 w-1.5 rounded-full ${config.cor}`} />
      {config.texto}
    </span>
  );
}
