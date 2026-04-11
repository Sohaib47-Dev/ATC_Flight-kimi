"""
Encryption Module for Secure ATC -> Defense Data Transfer
Uses symmetric encryption (Fernet) for basic security
"""
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import base64
import json
import os


class SecureTransfer:
    """
    Handles encryption and decryption of flight data
    Uses Fernet symmetric encryption
    """
    
    # Static key for demonstration (in production, use secure key management)
    _key = None
    
    @classmethod
    def _get_key(cls) -> bytes:
        """Get or generate encryption key"""
        if cls._key is None:
            # Use a static key derived from a passphrase for demo
            # In production, use environment variable or secure key store
            passphrase = b"Flight-Link-Secure-2024-ATC-Defense-Key"
            salt = b"flight_link_salt"  # In production, use random salt
            
            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=32,
                salt=salt,
                iterations=100000,
            )
            cls._key = base64.urlsafe_b64encode(kdf.derive(passphrase))
        
        return cls._key
    
    @classmethod
    def encrypt_data(cls, data: dict) -> str:
        """
        Encrypt dictionary data
        Returns base64-encoded encrypted string
        """
        key = cls._get_key()
        fernet = Fernet(key)
        
        # Convert data to JSON string
        json_data = json.dumps(data, default=str)
        
        # Encrypt
        encrypted = fernet.encrypt(json_data.encode('utf-8'))
        
        # Return base64-encoded string
        return base64.b64encode(encrypted).decode('utf-8')
    
    @classmethod
    def decrypt_data(cls, encrypted_str: str) -> dict:
        """
        Decrypt encrypted data string
        Returns original dictionary
        """
        try:
            key = cls._get_key()
            fernet = Fernet(key)
            
            # Decode base64
            encrypted_bytes = base64.b64decode(encrypted_str.encode('utf-8'))
            
            # Decrypt
            decrypted = fernet.decrypt(encrypted_bytes)
            
            # Parse JSON
            return json.loads(decrypted.decode('utf-8'))
        
        except Exception as e:
            raise ValueError(f"Decryption failed: {str(e)}")
    
    @classmethod
    def generate_key(cls) -> str:
        """Generate a new random key (for reference)"""
        return Fernet.generate_key().decode('utf-8')


class MockSecureTransfer:
    """
    Mock encryption for development/testing
    Simply base64 encodes the JSON data without actual encryption
    """
    
    @classmethod
    def encrypt_data(cls, data: dict) -> str:
        """Mock encrypt - just base64 encode"""
        json_data = json.dumps(data, default=str)
        return base64.b64encode(json_data.encode('utf-8')).decode('utf-8')
    
    @classmethod
    def decrypt_data(cls, encrypted_str: str) -> dict:
        """Mock decrypt - just base64 decode"""
        try:
            decoded = base64.b64decode(encrypted_str.encode('utf-8'))
            return json.loads(decoded.decode('utf-8'))
        except Exception as e:
            raise ValueError(f"Decoding failed: {str(e)}")


# Use real encryption by default
EncryptionManager = SecureTransfer


def encrypt_track_data(track_data: dict) -> str:
    """
    Convenience function to encrypt track data
    """
    return EncryptionManager.encrypt_data(track_data)


def decrypt_track_data(encrypted_data: str) -> dict:
    """
    Convenience function to decrypt track data
    """
    return EncryptionManager.decrypt_data(encrypted_data)
