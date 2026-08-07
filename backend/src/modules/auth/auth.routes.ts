import { Router } from 'express';

import { assincrono, autenticar, validarBody } from '../../middleware/index.js';
import * as controller from './auth.controller.js';
import {
  atualizarPerfilSchema,
  loginSchema,
  refreshSchema,
  registroSchema,
} from './auth.schemas.js';

export const authRoutes = Router();

authRoutes.post('/registro', validarBody(registroSchema), assincrono(controller.registrar));
authRoutes.post('/login', validarBody(loginSchema), assincrono(controller.login));
authRoutes.post('/refresh', validarBody(refreshSchema), assincrono(controller.renovar));
authRoutes.post('/sair', validarBody(refreshSchema), assincrono(controller.sair));

authRoutes.get('/eu', autenticar, assincrono(controller.eu));
authRoutes.patch('/eu', autenticar, validarBody(atualizarPerfilSchema), assincrono(controller.atualizar));
