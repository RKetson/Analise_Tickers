"""
backend/services/pluggy_service.py
Client HTTP assíncrono para comunicação com a API da Pluggy.ai.

Gerencia:
    - Autenticação (API Key com cache e renovação automática)
    - Connect Token para o widget meu.pluggy
    - CRUD de Items
    - Listagem de Accounts, Transactions (paginação por cursor),
      Investments e Investment Transactions

Todas as chamadas são feitas via httpx com TLS 1.2+ (verify=True).
"""

from __future__ import annotations

import time
from datetime import datetime
from typing import Any, Optional

import httpx

from backend.core.config import get_settings
from backend.core.logging import get_logger
from backend.core.security import mask_pii

logger = get_logger(__name__)


class PluggyServiceError(Exception):
    """Erro genérico do serviço Pluggy."""

    def __init__(self, message: str, status_code: int | None = None):
        self.status_code = status_code
        super().__init__(message)


class PluggyService:
    """Client assíncrono para a API da Pluggy.ai.

    Gerencia autenticação transparente com cache de token e
    renovação automática antes da expiração.
    """

    # Cache de API Key
    _api_key: str | None = None
    _api_key_expires_at: float = 0.0  # timestamp

    def __init__(self) -> None:
        settings = get_settings()
        self._base_url = settings.pluggy_base_url.rstrip("/")
        self._client_id = settings.pluggy_client_id
        self._client_secret = settings.pluggy_client_secret

    # =================================================================
    # HTTP Client
    # =================================================================

    def _get_client(self) -> httpx.AsyncClient:
        """Cria um httpx.AsyncClient com defaults seguros."""
        return httpx.AsyncClient(
            base_url=self._base_url,
            timeout=httpx.Timeout(30.0, connect=10.0),
            verify=True,  # TLS 1.2+ enforced
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
        )

    async def _request(
        self,
        method: str,
        path: str,
        *,
        json_data: dict | None = None,
        params: dict | None = None,
        authenticated: bool = True,
    ) -> dict | list:
        """Executa uma requisição HTTP autenticada.

        Args:
            method: GET, POST, PUT, PATCH, DELETE.
            path: Caminho da API (ex: /items).
            json_data: Body JSON.
            params: Query parameters.
            authenticated: Se True, inclui header Authorization com API Key.

        Returns:
            JSON de resposta parseado.

        Raises:
            PluggyServiceError: Em caso de erro HTTP ou resposta inesperada.
        """
        headers = {}
        if authenticated:
            api_key = await self._get_api_key()
            headers["X-API-KEY"] = api_key

        async with self._get_client() as client:
            try:
                response = await client.request(
                    method,
                    path,
                    json=json_data,
                    params=params,
                    headers=headers,
                )
            except httpx.RequestError as exc:
                logger.error(
                    "pluggy_request_error",
                    method=method,
                    path=path,
                    error=str(exc),
                )
                raise PluggyServiceError(f"Erro de conexão com Pluggy: {exc}")

        if response.status_code >= 400:
            error_body = response.text
            logger.error(
                "pluggy_api_error",
                method=method,
                path=path,
                status_code=response.status_code,
                response_body=mask_pii(error_body[:500]),
            )
            raise PluggyServiceError(
                f"Pluggy API error {response.status_code}: {error_body[:300]}",
                status_code=response.status_code,
            )

        if response.status_code == 204:
            return {}

        return response.json()

    # =================================================================
    # Autenticação
    # =================================================================

    async def _get_api_key(self) -> str:
        """Obtém API Key com cache (validade 2h, renova 5 min antes).

        Returns:
            API Key string.
        """
        # Renovar se faltam menos de 5 min para expirar
        if self._api_key and time.time() < (self._api_key_expires_at - 300):
            return self._api_key

        logger.info("pluggy_auth", action="requesting_new_api_key")

        data = await self._request(
            "POST",
            "/auth",
            json_data={
                "clientId": self._client_id,
                "clientSecret": self._client_secret,
            },
            authenticated=False,
        )

        self._api_key = data["apiKey"]
        # API Key válida por 2 horas (7200 segundos)
        self._api_key_expires_at = time.time() + 7200

        logger.info("pluggy_auth", action="api_key_obtained")
        return self._api_key

    async def create_connect_token(
        self,
        client_user_id: str | None = None,
        item_id: str | None = None,
    ) -> str:
        """Gera um connect_token para inicializar o widget meu.pluggy.

        O token tem validade de 30 minutos e escopo limitado.

        Args:
            client_user_id: ID do usuário para rastreabilidade.
            item_id: Se informado, gera token para atualizar item existente.

        Returns:
            access_token string para passar ao widget.
        """
        body: dict[str, Any] = {}
        if client_user_id:
            body["clientUserId"] = client_user_id
        if item_id:
            body["itemId"] = item_id

        data = await self._request("POST", "/connect_token", json_data=body)

        logger.info(
            "pluggy_connect_token",
            action="created",
            client_user_id=client_user_id or "default",
        )
        return data["accessToken"]

    # =================================================================
    # Items
    # =================================================================

    async def get_item(self, item_id: str) -> dict:
        """Busca detalhes de um Item (conexão com instituição).

        Args:
            item_id: ID do item na Pluggy.

        Returns:
            Dict com dados do item.
        """
        return await self._request("GET", f"/items/{item_id}")

    async def delete_item(self, item_id: str) -> bool:
        """Remove um Item e todos os dados associados na Pluggy.

        Args:
            item_id: ID do item.

        Returns:
            True se removido com sucesso.
        """
        await self._request("DELETE", f"/items/{item_id}")
        logger.info("pluggy_item", action="deleted", item_id=item_id)
        return True

    async def update_item(self, item_id: str) -> dict:
        """Força re-sincronização de um Item na Pluggy.

        Args:
            item_id: ID do item.

        Returns:
            Dict com dados atualizados do item.
        """
        data = await self._request("PATCH", f"/items/{item_id}")
        logger.info("pluggy_item", action="update_triggered", item_id=item_id)
        return data

    # =================================================================
    # Accounts
    # =================================================================

    async def list_accounts(self, item_id: str) -> list[dict]:
        """Lista todas as contas de um Item.

        Args:
            item_id: ID do item na Pluggy.

        Returns:
            Lista de dicts com dados das contas.
        """
        data = await self._request(
            "GET", "/accounts", params={"itemId": item_id}
        )
        results = data.get("results", [])
        logger.info(
            "pluggy_accounts",
            action="listed",
            item_id=item_id,
            count=len(results),
        )
        return results

    # =================================================================
    # Transactions (paginação por cursor)
    # =================================================================

    async def list_transactions(
        self,
        account_id: str,
        from_date: str | None = None,
        to_date: str | None = None,
        page_size: int = 500,
    ) -> list[dict]:
        """Lista TODAS as transações de uma conta, com paginação automática.

        Implementa paginação por cursor conforme recomendação da Pluggy.

        Args:
            account_id: ID da conta.
            from_date: Data inicial (YYYY-MM-DD).
            to_date: Data final (YYYY-MM-DD).
            page_size: Tamanho de cada página (max 500).

        Returns:
            Lista completa de transações.
        """
        all_transactions: list[dict] = []
        params: dict[str, Any] = {
            "accountId": account_id,
            "pageSize": min(page_size, 500),
        }
        if from_date:
            params["from"] = from_date
        if to_date:
            params["to"] = to_date

        page = 1
        while True:
            params["page"] = page
            data = await self._request("GET", "/transactions", params=params)
            results = data.get("results", [])
            all_transactions.extend(results)

            total_pages = data.get("totalPages", 1)
            if page >= total_pages:
                break
            page += 1

        logger.info(
            "pluggy_transactions",
            action="listed",
            account_id=account_id,
            total=len(all_transactions),
        )
        return all_transactions

    # =================================================================
    # Investments
    # =================================================================

    async def list_investments(self, item_id: str) -> list[dict]:
        """Lista todas as posições de investimento de um Item.

        Args:
            item_id: ID do item na Pluggy.

        Returns:
            Lista de dicts com dados dos investimentos.
        """
        data = await self._request(
            "GET", "/investments", params={"itemId": item_id}
        )
        results = data.get("results", [])
        logger.info(
            "pluggy_investments",
            action="listed",
            item_id=item_id,
            count=len(results),
        )
        return results

    async def list_investment_transactions(
        self,
        investment_id: str,
        page_size: int = 500,
    ) -> list[dict]:
        """Lista movimentações de um investimento específico.

        Args:
            investment_id: ID do investimento.
            page_size: Tamanho de cada página.

        Returns:
            Lista completa de movimentações.
        """
        all_txns: list[dict] = []
        params: dict[str, Any] = {"pageSize": min(page_size, 500)}

        page = 1
        while True:
            params["page"] = page
            data = await self._request(
                "GET",
                f"/investments/{investment_id}/transactions",
                params=params,
            )
            results = data.get("results", [])
            all_txns.extend(results)

            total_pages = data.get("totalPages", 1)
            if page >= total_pages:
                break
            page += 1

        logger.info(
            "pluggy_inv_transactions",
            action="listed",
            investment_id=investment_id,
            total=len(all_txns),
        )
        return all_txns

    # =================================================================
    # Identity
    # =================================================================

    async def get_identity(self, item_id: str) -> dict:
        """Busca dados de identidade (cadastro) do titular.

        ATENÇÃO: Retorna PII (CPF, nome, e-mail). Deve ser criptografado
        antes de persistir.

        Args:
            item_id: ID do item na Pluggy.

        Returns:
            Dict com dados de identidade.
        """
        data = await self._request(
            "GET", "/identity", params={"itemId": item_id}
        )
        logger.info(
            "pluggy_identity",
            action="fetched",
            item_id=item_id,
        )
        return data
