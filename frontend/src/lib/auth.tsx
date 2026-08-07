import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react';

import { api, lerSessao, limparSessao, salvarSessao } from './api';
import type { Sessao, Usuario } from './tipos';

interface ContextoAuth {
  usuario: Usuario | null;
  carregando: boolean;
  entrar: (email: string, senha: string) => Promise<void>;
  registrar: (dados: {
    nome: string;
    email: string;
    senha: string;
    capital: number;
  }) => Promise<void>;
  sair: () => Promise<void>;
  atualizarPerfil: (dados: { nome?: string; capital?: number }) => Promise<void>;
}

const Auth = createContext<ContextoAuth | null>(null);

export function ProvedorAuth({ children }: { children: ReactNode }) {
  const [usuario, setUsuario] = useState<Usuario | null>(() => lerSessao()?.usuario ?? null);
  const [carregando, setCarregando] = useState(true);

  // Revalida a sessão no boot. O `usuario` do localStorage é só para evitar o piscar da
  // tela de login; quem manda é o que o backend disser.
  useEffect(() => {
    let ativo = true;
    if (!lerSessao()) {
      setCarregando(false);
      return;
    }
    api
      .get<Usuario>('/auth/eu')
      .then((atual) => {
        if (!ativo) return;
        setUsuario(atual);
        const sessao = lerSessao();
        if (sessao) salvarSessao({ ...sessao, usuario: atual });
      })
      .catch(() => {
        if (ativo) setUsuario(null);
      })
      .finally(() => {
        if (ativo) setCarregando(false);
      });
    return () => {
      ativo = false;
    };
  }, []);

  // O cliente HTTP avisa quando a renovação falhou de vez. Sem isto a tela ficaria
  // mostrando dados velhos com todas as chamadas em 401.
  useEffect(() => {
    const aoExpirar = () => setUsuario(null);
    window.addEventListener('cronos:sessao-expirada', aoExpirar);
    return () => window.removeEventListener('cronos:sessao-expirada', aoExpirar);
  }, []);

  const entrar = useCallback(async (email: string, senha: string) => {
    const sessao = await api.post<Sessao>('/auth/login', { email, senha });
    salvarSessao(sessao);
    setUsuario(sessao.usuario);
  }, []);

  const registrar = useCallback(
    async (dados: { nome: string; email: string; senha: string; capital: number }) => {
      const sessao = await api.post<Sessao>('/auth/registro', dados);
      salvarSessao(sessao);
      setUsuario(sessao.usuario);
    },
    [],
  );

  const sair = useCallback(async () => {
    const sessao = lerSessao();
    if (sessao?.refreshToken) {
      // Revoga no servidor, mas nunca deixa uma falha de rede impedir o logout local.
      await api.post('/auth/sair', { refreshToken: sessao.refreshToken }).catch(() => {});
    }
    limparSessao();
    setUsuario(null);
  }, []);

  const atualizarPerfil = useCallback(async (dados: { nome?: string; capital?: number }) => {
    const atual = await api.patch<Usuario>('/auth/eu', dados);
    setUsuario(atual);
    const sessao = lerSessao();
    if (sessao) salvarSessao({ ...sessao, usuario: atual });
  }, []);

  const valor = useMemo(
    () => ({ usuario, carregando, entrar, registrar, sair, atualizarPerfil }),
    [usuario, carregando, entrar, registrar, sair, atualizarPerfil],
  );

  return <Auth.Provider value={valor}>{children}</Auth.Provider>;
}

export function useAuth(): ContextoAuth {
  const contexto = useContext(Auth);
  if (!contexto) throw new Error('useAuth precisa estar dentro de <ProvedorAuth>');
  return contexto;
}
