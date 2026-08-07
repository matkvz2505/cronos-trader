import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';

import { Alerta, Botao } from '../components/ui';
import { ErroApi } from '../lib/api';
import { useAuth } from '../lib/auth';

export function Registrar() {
  const { registrar } = useAuth();
  const navegar = useNavigate();
  const [dados, setDados] = useState({
    nome: '',
    email: '',
    senha: '',
    capital: 20_000,
  });
  const [erro, setErro] = useState<string | null>(null);
  const [campos, setCampos] = useState<Array<{ campo: string; mensagem: string }>>([]);
  const [enviando, setEnviando] = useState(false);

  async function enviar(evento: React.FormEvent) {
    evento.preventDefault();
    setErro(null);
    setCampos([]);
    setEnviando(true);
    try {
      await registrar(dados);
      navegar('/', { replace: true });
    } catch (e) {
      if (e instanceof ErroApi) {
        setErro(e.message);
        setCampos(e.campos ?? []);
      } else {
        setErro('Não foi possível criar a conta');
      }
    } finally {
      setEnviando(false);
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center px-4 py-12">
      <div className="w-full max-w-md space-y-6">
        <div className="text-center">
          <p className="text-4xl">📈</p>
          <h1 className="mt-3 text-2xl font-semibold tracking-tight">Criar conta</h1>
        </div>

        <form onSubmit={enviar} className="cartao space-y-4 p-6">
          {erro && (
            <Alerta tom="erro">
              {erro}
              {campos.length > 0 && (
                <ul className="mt-1 space-y-0.5">
                  {campos.map((c) => (
                    <li key={c.campo}>· {c.mensagem}</li>
                  ))}
                </ul>
              )}
            </Alerta>
          )}

          <label className="block">
            <span className="mb-1.5 block text-sm text-texto-suave">Nome</span>
            <input
              required
              className="campo"
              value={dados.nome}
              onChange={(e) => setDados({ ...dados, nome: e.target.value })}
            />
          </label>

          <label className="block">
            <span className="mb-1.5 block text-sm text-texto-suave">E-mail</span>
            <input
              type="email"
              required
              autoComplete="email"
              className="campo"
              value={dados.email}
              onChange={(e) => setDados({ ...dados, email: e.target.value })}
            />
          </label>

          <label className="block">
            <span className="mb-1.5 block text-sm text-texto-suave">Senha</span>
            <input
              type="password"
              required
              minLength={10}
              autoComplete="new-password"
              className="campo"
              value={dados.senha}
              onChange={(e) => setDados({ ...dados, senha: e.target.value })}
            />
            <span className="mt-1 block text-xs text-texto-fraco">Mínimo de 10 caracteres.</span>
          </label>

          <label className="block">
            <span className="mb-1.5 block text-sm text-texto-suave">Capital para operar</span>
            <input
              type="number"
              required
              min={1000}
              step={1000}
              className="campo numerico"
              value={dados.capital}
              onChange={(e) => setDados({ ...dados, capital: Number(e.target.value) })}
            />
            <span className="mt-1 block text-xs text-texto-fraco">
              Define quantos contratos cada sinal sugere, arriscando 1% por operação. Dá para
              mudar depois.
            </span>
          </label>

          <Botao type="submit" disabled={enviando} className="w-full">
            {enviando ? 'Criando…' : 'Criar conta'}
          </Botao>

          <p className="text-center text-sm text-texto-suave">
            Já tem conta?{' '}
            <Link to="/entrar" className="text-marca hover:underline">
              Entrar
            </Link>
          </p>
        </form>
      </div>
    </div>
  );
}
