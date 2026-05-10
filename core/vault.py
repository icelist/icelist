"""
加密保险箱 —— 主密码 Fernet 加密本地 JSON
存储：
  ~/.chain-sniper/vault.dat    （加密的钱包 + API key）
  ~/.chain-sniper/vault.meta   （salt，不含密码）

安全：
  - PBKDF2-HMAC-SHA256，100k iterations
  - Fernet (AES-128-CBC + HMAC-SHA256)
  - 解锁后密钥保存在内存，进程退出即消失
"""
from __future__ import annotations
import os
import json
import base64
from pathlib import Path
from typing import Any

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC


class VaultLockedError(RuntimeError):
    pass


class VaultNotInitializedError(RuntimeError):
    pass


class Vault:
    def __init__(self, root: Path | None = None):
        self.root = root or (Path.home() / ".chain-sniper")
        self.root.mkdir(parents=True, exist_ok=True)
        self.meta_file = self.root / "vault.meta"
        self.data_file = self.root / "vault.dat"
        self._key: bytes | None = None
        self._data: dict[str, Any] = {"wallets": [], "api": {}}

    # ---------- 状态 ----------

    def is_initialized(self) -> bool:
        return self.meta_file.exists() and self.data_file.exists()

    def is_locked(self) -> bool:
        return self._key is None

    # ---------- 初始化 / 解锁 ----------

    def init(self, master_password: str) -> None:
        """首次设置主密码"""
        if self.is_initialized():
            raise RuntimeError("Vault already initialized; use unlock")
        salt = os.urandom(16)
        self.meta_file.write_bytes(salt)
        self._key = self._derive_key(master_password, salt)
        self._data = {"wallets": [], "api": {}}
        self._save()

    def unlock(self, master_password: str) -> None:
        if not self.is_initialized():
            raise VaultNotInitializedError("Vault not initialized. Call init() first.")
        salt = self.meta_file.read_bytes()
        key = self._derive_key(master_password, salt)
        try:
            raw = Fernet(key).decrypt(self.data_file.read_bytes())
            self._data = json.loads(raw.decode())
            self._key = key
        except InvalidToken:
            raise ValueError("主密码错误")

    def lock(self) -> None:
        self._key = None
        self._data = {"wallets": [], "api": {}}

    def change_password(self, old: str, new: str) -> None:
        self.unlock(old)
        salt = os.urandom(16)
        self.meta_file.write_bytes(salt)
        self._key = self._derive_key(new, salt)
        self._save()

    # ---------- 钱包 ----------

    def list_wallets(self) -> list[dict]:
        self._check_unlocked()
        # 返回时只给地址预览，不返回私钥
        out = []
        for w in self._data["wallets"]:
            out.append({
                "chain": w["chain"],
                "label": w["label"],
                "address_preview": w.get("address_preview", "—"),
            })
        return out

    def add_wallet(self, chain: str, label: str, private_key: str) -> None:
        self._check_unlocked()
        # 去重
        self._data["wallets"] = [
            w for w in self._data["wallets"]
            if not (w["chain"] == chain and w["label"] == label)
        ]
        self._data["wallets"].append({
            "chain": chain,
            "label": label,
            "private_key": private_key,
            "address_preview": self._preview_address(chain, private_key),
        })
        self._save()

    def remove_wallet(self, chain: str, label: str) -> None:
        self._check_unlocked()
        self._data["wallets"] = [
            w for w in self._data["wallets"]
            if not (w["chain"] == chain and w["label"] == label)
        ]
        self._save()

    def get_private_key(self, chain: str, label: str = "default") -> str | None:
        """ONLY 内部调用 —— 不要在 UI 显示"""
        self._check_unlocked()
        for w in self._data["wallets"]:
            if w["chain"] == chain and w["label"] == label:
                return w["private_key"]
        return None

    # ---------- API / RPC 设置 ----------

    def get_api(self) -> dict:
        self._check_unlocked()
        return dict(self._data.get("api", {}))

    def set_api(self, mapping: dict) -> None:
        self._check_unlocked()
        self._data["api"] = mapping
        self._save()

    # ---------- 内部 ----------

    def _check_unlocked(self) -> None:
        if self.is_locked():
            raise VaultLockedError("Vault is locked")

    def _save(self) -> None:
        assert self._key is not None
        raw = json.dumps(self._data).encode()
        self.data_file.write_bytes(Fernet(self._key).encrypt(raw))

    @staticmethod
    def _derive_key(password: str, salt: bytes) -> bytes:
        kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32,
                         salt=salt, iterations=100_000)
        return base64.urlsafe_b64encode(kdf.derive(password.encode()))

    @staticmethod
    def _preview_address(chain: str, pk: str) -> str:
        """仅用于 UI 显示，不抛错（避免因为私钥格式错误导致导入失败）"""
        try:
            if chain in ("ethereum", "bsc"):
                from eth_account import Account
                if not pk.startswith("0x"):
                    pk = "0x" + pk
                addr = Account.from_key(pk).address
                return f"{addr[:8]}...{addr[-6:]}"
            if chain == "solana":
                try:
                    from solders.keypair import Keypair
                    import base58
                    kp = Keypair.from_bytes(base58.b58decode(pk))
                    addr = str(kp.pubkey())
                    return f"{addr[:6]}...{addr[-6:]}"
                except Exception:
                    return "—"
        except Exception:
            return "—"
        return "—"
