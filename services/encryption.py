"""密钥加密工具 - 使用 Fernet 对称加密"""
from cryptography.fernet import Fernet
import base64
import hashlib
from config.settings import settings


class EncryptionService:
    """密钥加密服务"""
    
    def __init__(self):
        # 从配置的密钥派生 Fernet 密钥（32 字节 URL-safe base64 编码）
        key_material = settings.ENCRYPTION_KEY.encode('utf-8')
        # 使用 SHA256 生成固定长度的密钥
        key_hash = hashlib.sha256(key_material).digest()
        # Fernet 需要 URL-safe base64 编码的 32 字节密钥
        self.fernet_key = base64.urlsafe_b64encode(key_hash)
        self.fernet = Fernet(self.fernet_key)
    
    def encrypt(self, plaintext: str) -> str:
        """
        加密字符串
        
        Args:
            plaintext: 明文字符串
            
        Returns:
            加密后的字符串（base64 编码）
        """
        if not plaintext:
            return ""
        
        encrypted_bytes = self.fernet.encrypt(plaintext.encode('utf-8'))
        return encrypted_bytes.decode('utf-8')
    
    def decrypt(self, encrypted_text: str) -> str:
        """
        解密字符串
        
        Args:
            encrypted_text: 加密的字符串（base64 编码）
            
        Returns:
            解密后的明文字符串
        """
        if not encrypted_text:
            return ""
        
        decrypted_bytes = self.fernet.decrypt(encrypted_text.encode('utf-8'))
        return decrypted_bytes.decode('utf-8')
    
    def rotate_key(self, old_key: str, new_key: str) -> tuple[Fernet, Fernet]:
        """
        生成密钥轮转所需的 Fernet 对象
        
        Args:
            old_key: 旧的加密密钥
            new_key: 新的加密密钥
            
        Returns:
            (old_fernet, new_fernet) 元组
        """
        old_key_hash = hashlib.sha256(old_key.encode('utf-8')).digest()
        new_key_hash = hashlib.sha256(new_key.encode('utf-8')).digest()
        
        old_fernet = Fernet(base64.urlsafe_b64encode(old_key_hash))
        new_fernet = Fernet(base64.urlsafe_b64encode(new_key_hash))
        
        return old_fernet, new_fernet


# 全局加密服务实例
encryption_service = EncryptionService()

