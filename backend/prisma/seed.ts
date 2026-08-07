/**
 * Seed de desenvolvimento.
 *
 * Cria um admin e um usuário comum. Idempotente — pode rodar quantas vezes quiser.
 * Não cria candles nem sinais: esses vêm do coletor MT5 ou do gerador sintético
 * (`ai/scripts/gerar_amostra.py`), e inventar sinal falso no banco daria a impressão de
 * que o motor está rodando quando não está.
 */
import { PrismaClient } from '@prisma/client';
import bcrypt from 'bcryptjs';

const prisma = new PrismaClient();

const USUARIOS = [
  {
    nome: 'Matheus Aroldo',
    email: 'matheus2aroldo@gmail.com',
    senha: 'Trader@2026!',
    papel: 'ADMIN' as const,
    capital: 50_000,
  },
  {
    nome: 'Operador Teste',
    email: 'operador@cronos.trader',
    senha: 'Operador@123',
    papel: 'USUARIO' as const,
    capital: 20_000,
  },
];

async function main(): Promise<void> {
  for (const dados of USUARIOS) {
    const senhaHash = await bcrypt.hash(dados.senha, 12);
    await prisma.usuario.upsert({
      where: { email: dados.email },
      create: {
        nome: dados.nome,
        email: dados.email,
        senhaHash,
        papel: dados.papel,
        capital: dados.capital,
      },
      // Não sobrescreve a senha de quem já existe: rodar o seed num banco em uso não
      // pode resetar credencial silenciosamente.
      update: { nome: dados.nome, papel: dados.papel },
    });
    console.log(`  usuário ${dados.email} (${dados.papel})`);
  }

  console.log('\nCredenciais de desenvolvimento:');
  for (const u of USUARIOS) console.log(`  ${u.email} / ${u.senha}`);
  console.log('\nTroque antes de expor qualquer coisa fora da sua máquina.');
}

main()
  .catch((erro) => {
    console.error(erro);
    process.exit(1);
  })
  .finally(() => prisma.$disconnect());
