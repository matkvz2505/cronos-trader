import { useEffect, useState } from 'react';

import { Alerta, Cartao, Carregando, Desempenho, Titulo } from '../components/ui';
import { api } from '../lib/api';
import { percentual } from '../lib/formato';
import type { DesempenhoPadrao } from '../lib/tipos';

interface NivelFib {
  nivel: number;
  razao: number;
  relevancia: number;
}

interface Estudos {
  fibonacci: {
    metodo: string;
    amostra: string;
    corte: number;
    porAtivo: Array<{ ativo: string; usaFibonacci: boolean; niveis: NivelFib[] }>;
    conclusao: string;
  };
  medias: {
    conjunto: Array<{ nome: string; periodo: number; papel: string }>;
    comoEntra: string;
  };
  janelas: Array<{
    rotulo: string;
    inicio: string;
    fim: string;
    peso: number;
    opera: boolean;
  }>;
  avisoJanelas: string;
}

/**
 * A página que explica **por que o motor pesa o que pesa**.
 *
 * Existe porque um score sem procedência é um número que o operador tem que aceitar por
 * fé. Aqui ele vê a medição por trás de cada fator — inclusive, e principalmente, onde a
 * medição contradiz o que o mercado repete.
 */
export function Estudos() {
  const [estudos, setEstudos] = useState<Estudos | null>(null);
  const [desempenho, setDesempenho] = useState<DesempenhoPadrao[]>([]);
  const [erro, setErro] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([
      api.get<Estudos>('/mercado/estudos'),
      api.get<DesempenhoPadrao[]>('/sinais/desempenho'),
    ])
      .then(([e, d]) => {
        setEstudos(e);
        setDesempenho(d);
      })
      .catch((e) => setErro(e instanceof Error ? e.message : 'Motor fora do ar'));
  }, []);

  if (erro) return <Alerta tom="erro">{erro}</Alerta>;
  if (!estudos) return <Carregando texto="carregando medições…" />;

  return (
    <div className="space-y-8">
      <header className="surge">
        <h1 className="text-2xl font-semibold">Estudos</h1>
        <p className="mt-1 max-w-2xl text-sm text-texto-suave">
          O motor não pontua por convenção. Cada fator abaixo foi medido nos seus dados — e
          onde a medição contradiz o que o mercado repete, o código segue a medição.
        </p>
      </header>

      {/* --- Fibonacci --- */}
      <section className="surge">
        <Titulo>Fibonacci — o que WIN e WDO realmente respeitam</Titulo>

        <div className="grid gap-4 lg:grid-cols-[1fr_1.15fr]">
          <Cartao>
            <p className="rotulo mb-2">Método</p>
            <p className="text-[13px] leading-relaxed text-texto-suave">
              {estudos.fibonacci.metodo}
            </p>
            <div className="divisor my-3.5" />
            <p className="rotulo mb-1">Amostra</p>
            <p className="numerico text-sm text-texto">{estudos.fibonacci.amostra}</p>
            <p className="mt-3 text-xs text-texto-fraco">
              Corte de destaque: {estudos.fibonacci.corte.toFixed(2)}× a vizinhança imediata.
            </p>
          </Cartao>

          <div className="space-y-3">
            {estudos.fibonacci.porAtivo.map((a) => (
              <Cartao key={a.ativo} className={a.usaFibonacci ? '' : 'opacity-90'}>
                <div className="mb-3 flex items-center justify-between">
                  <h3 className="numerico text-lg font-semibold">{a.ativo}</h3>
                  <span
                    className={`rounded-md px-2.5 py-1 text-xs font-semibold ${
                      a.usaFibonacci
                        ? 'bg-alta-fundo text-alta'
                        : 'bg-superficie-topo text-texto-fraco'
                    }`}
                  >
                    {a.usaFibonacci ? 'usa Fibonacci' : 'não usa Fibonacci'}
                  </span>
                </div>

                {a.niveis.length === 0 ? (
                  <p className="text-[13px] leading-relaxed text-texto-suave">
                    Nenhum nível produziu pico local em 5 minutos. O motor{' '}
                    <strong className="text-texto">não dá bônus de Fibonacci</strong> neste
                    ativo — deixar de pontuar onde não há evidência não é o motor ficando
                    pior, é ele parando de inventar confluência.
                  </p>
                ) : (
                  <ul className="space-y-2">
                    {a.niveis.map((n) => (
                      <li key={n.nivel} className="flex items-center gap-3">
                        <span className="numerico w-16 text-sm font-semibold text-marca">
                          {percentual(n.nivel, 1)}
                        </span>
                        <div className="h-2 flex-1 overflow-hidden rounded-full bg-superficie-topo">
                          <div
                            className="h-full rounded-full bg-marca"
                            style={{ width: `${Math.min(100, (n.razao / 2) * 100)}%` }}
                          />
                        </div>
                        <span className="numerico w-14 text-right text-sm text-texto">
                          {n.razao.toFixed(2)}×
                        </span>
                      </li>
                    ))}
                  </ul>
                )}
              </Cartao>
            ))}
          </div>
        </div>

        <Alerta tom="info" className="mt-4">
          {estudos.fibonacci.conclusao}
        </Alerta>
      </section>

      {/* --- Médias --- */}
      <section className="surge">
        <Titulo>Médias móveis — quatro papéis, não quatro versões da mesma coisa</Titulo>
        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          {estudos.medias.conjunto.map((m) => (
            <Cartao key={m.nome}>
              <p className="numerico text-base font-semibold text-marca">{m.nome}</p>
              <p className="mt-2 text-[13px] leading-relaxed text-texto-suave">{m.papel}</p>
            </Cartao>
          ))}
        </div>
        <Alerta tom="info" className="mt-3">
          {estudos.medias.comoEntra}
        </Alerta>
      </section>

      {/* --- Janelas do pregão --- */}
      <section className="surge">
        <Titulo>Janelas do pregão</Titulo>
        <Cartao className="overflow-x-auto p-0">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-borda text-left">
                <th className="rotulo px-4 py-3 font-medium">Janela</th>
                <th className="rotulo px-3 py-3 font-medium">Horário</th>
                <th className="rotulo px-3 py-3 text-right font-medium">Peso</th>
                <th className="rotulo px-4 py-3 font-medium">Opera?</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-borda">
              {estudos.janelas.map((j) => (
                <tr key={j.rotulo}>
                  <td className="px-4 py-2.5">{j.rotulo}</td>
                  <td className="numerico px-3 py-2.5 text-texto-suave">
                    {j.inicio}–{j.fim}
                  </td>
                  <td
                    className={`numerico px-3 py-2.5 text-right ${
                      j.peso > 1 ? 'text-alta' : j.peso < 1 ? 'text-baixa' : 'text-texto'
                    }`}
                  >
                    {j.peso.toFixed(2)}×
                  </td>
                  <td className="px-4 py-2.5">
                    {j.opera ? (
                      <span className="text-alta">sim</span>
                    ) : (
                      <span className="text-texto-fraco">não abre posição</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </Cartao>
        <Alerta tom="aviso" className="mt-3">
          {estudos.avisoJanelas}
        </Alerta>
      </section>

      {/* --- Placar dos padrões --- */}
      <section className="surge">
        <Titulo>Placar dos padrões — o que a sua conta viveu</Titulo>
        {desempenho.length === 0 ? (
          <Cartao>
            <p className="text-sm text-texto-suave">
              Sem operações encerradas ainda. O placar aparece conforme os sinais forem
              batendo alvo ou stop — é o número que decide qual padrão fica e qual sai.
            </p>
          </Cartao>
        ) : (
          <Cartao className="overflow-x-auto p-0">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-borda text-left">
                  <th className="rotulo px-4 py-3 font-medium">Padrão</th>
                  <th className="rotulo px-3 py-3 text-right font-medium">n</th>
                  <th className="rotulo px-4 py-3 font-medium">Acerto e expectância</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-borda">
                {desempenho.map((p) => (
                  <tr key={p.padraoId}>
                    <td className="px-4 py-2.5">{p.nome}</td>
                    <td className="numerico px-3 py-2.5 text-right text-texto-suave">
                      {p.ocorrencias}
                    </td>
                    <td className="px-4 py-2.5">
                      <Desempenho
                        taxa={p.taxaAcerto}
                        expectancia={p.expectanciaR}
                        suficiente={p.suficiente}
                      />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </Cartao>
        )}
      </section>
    </div>
  );
}
