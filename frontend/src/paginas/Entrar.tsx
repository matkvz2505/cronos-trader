import { useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';

import { Alerta, Botao } from '../components/ui';
import { api, ErroApi } from '../lib/api';
import { useAuth } from '../lib/auth';
import type { Saude } from '../lib/tipos';

/**
 * Login com verificação de saúde da stack.
 *
 * O status aparece **antes** de o usuário tentar entrar de propósito: descobrir que o
 * motor está fora depois de logar, clicar em analisar e esperar dois minutos de timeout é
 * uma experiência muito pior do que ler um aviso na porta de entrada.
 */
export function Entrar() {
  const { entrar, usuario } = useAuth();
  const navegar = useNavigate();
  const [email, setEmail] = useState('');
  const [senha, setSenha] = useState('');
  const [erro, setErro] = useState<string | null>(null);
  const [enviando, setEnviando] = useState(false);
  const [saude, setSaude] = useState<Saude | null>(null);

  useEffect(() => {
    if (usuario) navegar('/', { replace: true });
  }, [usuario, navegar]);

  useEffect(() => {
    api.get<Saude>('/mercado/saude').then(setSaude).catch(() => setSaude(null));
  }, []);

  async function enviar(evento: React.FormEvent) {
    evento.preventDefault();
    setErro(null);
    setEnviando(true);
    try {
      await entrar(email, senha);
      navegar('/', { replace: true });
    } catch (e) {
      setErro(e instanceof ErroApi ? e.message : 'Não foi possível entrar');
    } finally {
      setEnviando(false);
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center px-4 py-12">
      <div className="w-full max-w-md space-y-6">
        <div className="text-center">
          <p className="text-4xl">📈</p>
          <h1 className="mt-3 text-2xl font-semibold tracking-tight">
            Cronos <span className="text-marca">Trader</span>
          </h1>
          <p className="mt-1 text-sm text-texto-suave">
            Padrões de candlestick para mini-índice e mini-dólar
          </p>
        </div>

        <form onSubmit={enviar} className="cartao space-y-4 p-6">
          {erro && <Alerta tom="erro">{erro}</Alerta>}

          <label className="block">
            <span className="mb-1.5 block text-sm text-texto-suave">E-mail</span>
            <input
              type="email"
              required
              autoComplete="email"
              className="campo"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="voce@email.com"
            />
          </label>

          <label className="block">
            <span className="mb-1.5 block text-sm text-texto-suave">Senha</span>
            <input
              type="password"
              required
              autoComplete="current-password"
              className="campo"
              value={senha}
              onChange={(e) => setSenha(e.target.value)}
              placeholder="••••••••••"
            />
          </label>

          <Botao type="submit" disabled={enviando} className="w-full">
            {enviando ? 'Entrando…' : 'Entrar'}
          </Botao>

          <p className="text-center text-sm text-texto-suave">
            Ainda não tem conta?{' '}
            <Link to="/registrar" className="text-marca hover:underline">
              Criar conta
            </Link>
          </p>
        </form>

        <EstadoDaStack saude={saude} />
      </div>
    </div>
  );
}

function EstadoDaStack({ saude }: { saude: Saude | null }) {
  if (!saude) {
    return (
      <p className="text-center text-xs text-texto-fraco">
        Backend fora do ar. Suba com <code className="text-texto-suave">npm run dev</code> em{' '}
        <code className="text-texto-suave">backend/</code>.
      </p>
    );
  }

  const motorOk = 'ok' in saude.motor && saude.motor.ok;
  const mt5 = 'mt5' in saude.motor ? saude.motor.mt5 : undefined;
  const totalCandles = (saude.candles ?? []).reduce((soma, c) => soma + c.total, 0);

  return (
    <div className="cartao space-y-2 p-4 text-xs">
      <p className="tracking-wide text-texto-fraco uppercase">Estado da stack</p>
      <Linha rotulo="Banco de dados" ok={saude.banco} />
      <Linha rotulo="Motor de análise" ok={motorOk} detalhe={motorOk ? undefined : 'inicie ai/'} />
      <Linha
        rotulo="Coletor MT5"
        ok={mt5?.disponivel ?? false}
        detalhe={mt5?.detalhe ?? 'motor fora do ar'}
      />
      <Linha
        rotulo="Candles no banco"
        ok={totalCandles > 0}
        detalhe={totalCandles > 0 ? totalCandles.toLocaleString('pt-BR') : 'nenhum — rode o coletor'}
      />
    </div>
  );
}

function Linha({ rotulo, ok, detalhe }: { rotulo: string; ok: boolean; detalhe?: string }) {
  return (
    <div className="flex items-center justify-between gap-3">
      <span className="text-texto-suave">{rotulo}</span>
      <span className="flex min-w-0 items-center gap-1.5">
        {detalhe && <span className="truncate text-texto-fraco">{detalhe}</span>}
        <span className={`h-1.5 w-1.5 shrink-0 rounded-full ${ok ? 'bg-alta' : 'bg-baixa'}`} />
      </span>
    </div>
  );
}
