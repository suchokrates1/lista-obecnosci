"""
KSeF API Client Module
Moduł do komunikacji z API Krajowego Systemu e-Faktur
"""
import os
import logging
import requests
from typing import Dict, Optional, Tuple
from datetime import datetime
import json
import hashlib
import base64

logger = logging.getLogger(__name__)

# Adresy API KSeF dla różnych środowisk
KSEF_ENVIRONMENTS = {
    'production': 'https://ksef.mf.gov.pl/api',
    'demo': 'https://ksef-demo.mf.gov.pl/api',
    'test': 'https://ksef-test.mf.gov.pl/api',
}


class KSeFException(Exception):
    """Wyjątek dla błędów związanych z KSeF."""
    pass


class KSeFClient:
    """Klient do komunikacji z API KSeF."""
    
    def __init__(self, environment: str = 'test', nip: Optional[str] = None, token: Optional[str] = None):
        """
        Inicjalizuje klienta KSeF.
        
        Args:
            environment: Środowisko (test, demo, production)
            nip: NIP podatnika
            token: Token autoryzacyjny
        """
        if environment not in KSEF_ENVIRONMENTS:
            raise KSeFException(f"Invalid environment: {environment}")
        
        self.base_url = KSEF_ENVIRONMENTS[environment]
        self.environment = environment
        self.nip = nip or os.getenv('KSEF_NIP', '')
        self.token = token or os.getenv('KSEF_TOKEN', '')
        self.session_token: Optional[str] = None
        
        if not self.nip:
            raise KSeFException("NIP is required for KSeF API")
    
    def _get_headers(self, with_session: bool = False) -> Dict[str, str]:
        """Zwraca nagłówki HTTP dla żądań."""
        headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json',
        }
        
        if with_session and self.session_token:
            headers['SessionToken'] = self.session_token
        
        return headers
    
    def authorize_by_token(self) -> bool:
        """
        Autoryzacja przez token (bez certyfikatu).
        
        Returns:
            bool: True jeśli autoryzacja udana
        """
        url = f"{self.base_url}/online/Session/AuthorisationChallenge"
        
        payload = {
            'ContextIdentifier': {
                'type': 'onip',
                'identifier': self.nip
            }
        }
        
        try:
            response = requests.post(url, json=payload, headers=self._get_headers())
            response.raise_for_status()
            
            data = response.json()
            challenge = data.get('Challenge')
            
            if not challenge:
                raise KSeFException("No challenge received from KSeF")
            
            # W produkcji tutaj należy podpisać challenge certyfikatem kwalifikowanym
            # W środowisku testowym możemy użyć tokena
            timestamp = datetime.now().isoformat()
            
            # Inicjalizacja sesji
            init_url = f"{self.base_url}/online/Session/InitToken"
            init_payload = {
                'ContextIdentifier': {
                    'type': 'onip',
                    'identifier': self.nip
                },
                'Token': self.token
            }
            
            init_response = requests.post(init_url, json=init_payload, headers=self._get_headers())
            init_response.raise_for_status()
            
            init_data = init_response.json()
            self.session_token = init_data.get('SessionToken', {}).get('Token')
            
            if not self.session_token:
                raise KSeFException("Failed to obtain session token")
            
            logger.info(f"KSeF session authorized successfully for NIP {self.nip}")
            return True
            
        except requests.exceptions.RequestException as e:
            logger.error(f"KSeF authorization failed: {e}")
            raise KSeFException(f"Authorization failed: {e}")
    
    def send_invoice(self, invoice_xml: str) -> Tuple[bool, Optional[str], Optional[str]]:
        """
        Wysyła fakturę do KSeF.
        
        Args:
            invoice_xml: XML faktury w formacie FA(2)
        
        Returns:
            Tuple[bool, Optional[str], Optional[str]]: 
                (sukces, numer referencyjny faktury, komunikat błędu)
        """
        if not self.session_token:
            try:
                self.authorize_by_token()
            except KSeFException as e:
                return False, None, str(e)
        
        url = f"{self.base_url}/online/Invoice/Send"
        
        try:
            # Kodowanie XML w base64
            invoice_bytes = invoice_xml.encode('utf-8')
            invoice_b64 = base64.b64encode(invoice_bytes).decode('utf-8')
            
            # Obliczenie SHA-256 hash
            sha256_hash = hashlib.sha256(invoice_bytes).hexdigest()
            
            payload = {
                'invoiceHash': {
                    'hashSHA': {
                        'algorithm': 'SHA-256',
                        'encoding': 'Base64',
                        'value': sha256_hash
                    },
                    'fileSize': len(invoice_bytes)
                },
                'invoicePayload': {
                    'type': 'plain',
                    'invoiceBody': invoice_b64
                }
            }
            
            response = requests.put(
                url, 
                json=payload, 
                headers=self._get_headers(with_session=True)
            )
            
            if response.status_code == 200 or response.status_code == 201:
                data = response.json()
                reference_number = data.get('ReferenceNumber')
                logger.info(f"Invoice sent successfully. Reference: {reference_number}")
                return True, reference_number, None
            else:
                error_msg = f"Failed to send invoice: {response.status_code} - {response.text}"
                logger.error(error_msg)
                return False, None, error_msg
                
        except requests.exceptions.RequestException as e:
            error_msg = f"Error sending invoice: {e}"
            logger.error(error_msg)
            return False, None, error_msg
    
    def get_invoice_status(self, reference_number: str) -> Optional[Dict]:
        """
        Pobiera status faktury.
        
        Args:
            reference_number: Numer referencyjny faktury
        
        Returns:
            Optional[Dict]: Dane statusu faktury lub None
        """
        if not self.session_token:
            self.authorize_by_token()
        
        url = f"{self.base_url}/online/Invoice/Status/{reference_number}"
        
        try:
            response = requests.get(url, headers=self._get_headers(with_session=True))
            response.raise_for_status()
            
            return response.json()
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Error getting invoice status: {e}")
            return None
    
    def terminate_session(self) -> bool:
        """
        Kończy sesję z KSeF.
        
        Returns:
            bool: True jeśli zakończenie sesji udane
        """
        if not self.session_token:
            return True
        
        url = f"{self.base_url}/online/Session/Terminate"
        
        try:
            response = requests.get(url, headers=self._get_headers(with_session=True))
            response.raise_for_status()
            
            self.session_token = None
            logger.info("KSeF session terminated successfully")
            return True
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Error terminating session: {e}")
            return False


def send_invoice_to_ksef(invoice_xml: str) -> Tuple[bool, Optional[str], Optional[str]]:
    """
    Wysyła fakturę do KSeF używając konfiguracji ze zmiennych środowiskowych.
    
    Args:
        invoice_xml: XML faktury w formacie FA(2)
    
    Returns:
        Tuple[bool, Optional[str], Optional[str]]: 
            (sukces, numer referencyjny, komunikat błędu)
    """
    environment = os.getenv('KSEF_ENVIRONMENT', 'test')
    nip = os.getenv('KSEF_NIP', '')
    token = os.getenv('KSEF_TOKEN', '')
    
    if not nip:
        return False, None, "KSEF_NIP not configured"
    
    try:
        client = KSeFClient(environment=environment, nip=nip, token=token)
        success, ref_number, error = client.send_invoice(invoice_xml)
        client.terminate_session()
        
        return success, ref_number, error
        
    except Exception as e:
        logger.exception("Unexpected error sending invoice to KSeF")
        return False, None, str(e)
