/**
 * Erros de domínio com código HTTP embutido.
 *
 * Existem para que o service possa recusar sem conhecer Express: `throw new NaoAutorizado()`
 * em vez de receber `res` como parâmetro. O middleware de erro traduz para resposta.
 */
export class ErroHttp extends Error {
  constructor(
    readonly status: number,
    message: string,
    readonly codigo: string,
    readonly detalhes?: unknown,
  ) {
    super(message);
    this.name = new.target.name;
  }
}

export class RequisicaoInvalida extends ErroHttp {
  constructor(mensagem = 'Requisição inválida', detalhes?: unknown) {
    super(400, mensagem, 'REQUISICAO_INVALIDA', detalhes);
  }
}

export class NaoAutorizado extends ErroHttp {
  constructor(mensagem = 'Credenciais inválidas') {
    super(401, mensagem, 'NAO_AUTORIZADO');
  }
}

export class Proibido extends ErroHttp {
  constructor(mensagem = 'Acesso negado') {
    super(403, mensagem, 'PROIBIDO');
  }
}

export class NaoEncontrado extends ErroHttp {
  constructor(recurso = 'Recurso') {
    super(404, `${recurso} não encontrado`, 'NAO_ENCONTRADO');
  }
}

export class Conflito extends ErroHttp {
  constructor(mensagem: string) {
    super(409, mensagem, 'CONFLITO');
  }
}

/** O serviço de IA está fora do ar ou demorou demais. Distinto de erro nosso. */
export class MotorIndisponivel extends ErroHttp {
  constructor(mensagem = 'Motor de análise indisponível') {
    super(503, mensagem, 'MOTOR_INDISPONIVEL');
  }
}
