"""
Tests for client-side session state management and role resolution.

Verifies JWT parsing, session creation, and UI flag resolution.
"""

import json
import base64
from pathlib import Path


class TestSessionTypes:
    """Test session type definitions."""
    
    def test_session_file_exists(self):
        """Verify session.ts file exists."""
        session_path = Path("/workspace/app/state/session.ts")
        assert session_path.exists(), "session.ts should exist"
    
    def test_user_session_interface_defined(self):
        """Verify UserSession interface is defined."""
        session_path = Path("/workspace/app/state/session.ts")
        content = session_path.read_text()
        
        assert "interface UserSession" in content
        
        # Check required fields
        assert "userId" in content
        assert "email" in content
        assert "roles" in content
        assert "uiFlags" in content
        assert "isAuthenticated" in content
        assert "isAnonymous" in content
        assert "token" in content
        assert "apiKey" in content
    
    def test_anonymous_session_defined(self):
        """Verify ANONYMOUS_SESSION constant is defined."""
        session_path = Path("/workspace/app/state/session.ts")
        content = session_path.read_text()
        
        assert "ANONYMOUS_SESSION" in content
        
        # Find ANONYMOUS_SESSION definition
        start = content.find("export const ANONYMOUS_SESSION")
        end = content.find("};", start) + 2
        anonymous_block = content[start:end]
        
        assert "isAuthenticated: false" in anonymous_block
        assert "isAnonymous: true" in anonymous_block
        assert "ROLE_GENERAL" in anonymous_block


class TestJWTParsing:
    """Test JWT token parsing functionality."""
    
    def test_parse_jwt_function_exists(self):
        """Verify parseJWT function is defined."""
        session_path = Path("/workspace/app/state/session.ts")
        content = session_path.read_text()
        
        assert "function parseJWT" in content
        assert "JWTPayload" in content
    
    def test_jwt_payload_interface_defined(self):
        """Verify JWTPayload interface is defined."""
        session_path = Path("/workspace/app/state/session.ts")
        content = session_path.read_text()
        
        assert "interface JWTPayload" in content
        
        # Find interface definition
        start = content.find("interface JWTPayload")
        end = content.find("}", start)
        interface_block = content[start:end]
        
        assert "sub" in interface_block  # User ID
        assert "email" in interface_block
        assert "roles" in interface_block
        assert "exp" in interface_block  # Expiration
    
    def test_jwt_expiration_check_exists(self):
        """Verify JWT expiration checking function."""
        session_path = Path("/workspace/app/state/session.ts")
        content = session_path.read_text()
        
        assert "function isJWTExpired" in content
        assert "payload.exp" in content
    
    def test_parse_jwt_handles_invalid_tokens(self):
        """Verify parseJWT handles invalid tokens gracefully."""
        session_path = Path("/workspace/app/state/session.ts")
        content = session_path.read_text()
        
        # Find parseJWT function
        start = content.find("function parseJWT")
        end = content.find("\n}", start)
        func_block = content[start:end]
        
        # Should have error handling
        assert "try" in func_block
        assert "catch" in func_block
        assert "return null" in func_block or "null" in func_block


class TestRoleResolution:
    """Test role resolution from JWT/API keys."""
    
    def test_get_user_role_function_exists(self):
        """Verify getUserRole function is defined."""
        session_path = Path("/workspace/app/state/session.ts")
        content = session_path.read_text()
        
        assert "function getUserRole" in content
        assert "token: string | null" in content
        assert ": Role" in content
    
    def test_get_user_role_returns_general_for_null_token(self):
        """Verify getUserRole returns general for null token."""
        session_path = Path("/workspace/app/state/session.ts")
        content = session_path.read_text()
        
        # Find getUserRole function
        start = content.find("function getUserRole")
        end = content.find("\n}", start)
        func_block = content[start:end]
        
        # Should check for null token
        assert "!token" in func_block
        assert "ROLE_GENERAL" in func_block
    
    def test_get_user_role_handles_expired_tokens(self):
        """Verify getUserRole handles expired tokens."""
        session_path = Path("/workspace/app/state/session.ts")
        content = session_path.read_text()
        
        # Find getUserRole function
        start = content.find("function getUserRole")
        end = content.find("\n}", start)
        func_block = content[start:end]
        
        assert "isJWTExpired" in func_block or "expired" in func_block.lower()
    
    def test_get_user_roles_returns_array(self):
        """Verify getUserRoles returns array of roles."""
        session_path = Path("/workspace/app/state/session.ts")
        content = session_path.read_text()
        
        assert "function getUserRoles" in content
        assert ": string[]" in content
    
    def test_get_user_roles_falls_back_to_general(self):
        """Verify getUserRoles falls back to [general]."""
        session_path = Path("/workspace/app/state/session.ts")
        content = session_path.read_text()
        
        # Find getUserRoles function
        start = content.find("function getUserRoles")
        end = content.find("\n}", start)
        func_block = content[start:end]
        
        # Should return array with ROLE_GENERAL
        assert "[ROLE_GENERAL]" in func_block


class TestUIFlagResolution:
    """Test UI flag resolution based on roles."""
    
    def test_resolve_ui_flags_for_roles_exists(self):
        """Verify resolveUIFlagsForRoles function exists."""
        session_path = Path("/workspace/app/state/session.ts")
        content = session_path.read_text()
        
        assert "function resolveUIFlagsForRoles" in content
        assert "roles: string[]" in content
        assert "UIFlags" in content
    
    def test_flags_computed_from_capabilities(self):
        """Verify flags are computed from user capabilities."""
        session_path = Path("/workspace/app/state/session.ts")
        content = session_path.read_text()
        
        # Find resolveUIFlagsForRoles function
        start = content.find("function resolveUIFlagsForRoles")
        end = content.find("\n}", start)
        func_block = content[start:end]
        
        # Should get aggregate capabilities
        assert "getAggregateCapabilities" in func_block or "capabilities" in func_block
        
        # Should compute flags based on capabilities
        assert "show_ledger" in func_block
        assert "CAP_READ_LEDGER_FULL" in func_block
    
    def test_show_ledger_requires_read_ledger_full(self):
        """Verify show_ledger flag requires CAP_READ_LEDGER_FULL."""
        session_path = Path("/workspace/app/state/session.ts")
        content = session_path.read_text()
        
        # Find resolveUIFlagsForRoles function
        start = content.find("function resolveUIFlagsForRoles")
        end = content.find("\n}", start)
        func_block = content[start:end]
        
        # show_ledger should be tied to CAP_READ_LEDGER_FULL
        assert "show_ledger" in func_block
        
        # Find show_ledger assignment
        ledger_line_start = func_block.find("show_ledger:")
        ledger_line_end = func_block.find(",", ledger_line_start)
        ledger_line = func_block[ledger_line_start:ledger_line_end]
        
        assert "CAP_READ_LEDGER_FULL" in ledger_line
    
    def test_show_debug_requires_view_debug(self):
        """Verify show_debug flag requires CAP_VIEW_DEBUG."""
        session_path = Path("/workspace/app/state/session.ts")
        content = session_path.read_text()
        
        # Find resolveUIFlagsForRoles function
        start = content.find("function resolveUIFlagsForRoles")
        end = content.find("\n}", start)
        func_block = content[start:end]
        
        # show_debug should be tied to CAP_VIEW_DEBUG
        debug_line_start = func_block.find("show_debug:")
        debug_line_end = func_block.find(",", debug_line_start)
        debug_line = func_block[debug_line_start:debug_line_end]
        
        assert "CAP_VIEW_DEBUG" in debug_line
    
    def test_server_flags_override_computed_flags(self):
        """Verify server flags can override computed flags."""
        session_path = Path("/workspace/app/state/session.ts")
        content = session_path.read_text()
        
        # Find resolveUIFlagsForRoles function
        start = content.find("function resolveUIFlagsForRoles")
        end = content.find("\n}", start)
        func_block = content[start:end]
        
        # Should merge computed with server flags
        assert "serverFlags" in func_block
        assert "..." in func_block  # Spread operator


class TestSessionManagement:
    """Test session creation and management."""
    
    def test_create_session_from_jwt_exists(self):
        """Verify createSessionFromJWT function exists."""
        session_path = Path("/workspace/app/state/session.ts")
        content = session_path.read_text()
        
        assert "function createSessionFromJWT" in content
        assert "token: string" in content
        assert ": UserSession" in content
    
    def test_create_session_from_jwt_parses_token(self):
        """Verify createSessionFromJWT parses JWT token."""
        session_path = Path("/workspace/app/state/session.ts")
        content = session_path.read_text()
        
        # Find function
        start = content.find("function createSessionFromJWT")
        end = content.find("\n}", start)
        func_block = content[start:end]
        
        assert "parseJWT" in func_block
        assert "getUserRoles" in func_block or "roles" in func_block
        assert "resolveUIFlagsForRoles" in func_block or "uiFlags" in func_block
    
    def test_create_session_from_jwt_handles_expired(self):
        """Verify createSessionFromJWT handles expired tokens."""
        session_path = Path("/workspace/app/state/session.ts")
        content = session_path.read_text()
        
        # Find function
        start = content.find("function createSessionFromJWT")
        end = content.find("\n}", start)
        func_block = content[start:end]
        
        # Should check expiration
        assert "isJWTExpired" in func_block or "expired" in func_block.lower()
        assert "ANONYMOUS_SESSION" in func_block
    
    def test_create_session_from_api_key_exists(self):
        """Verify createSessionFromAPIKey function exists."""
        session_path = Path("/workspace/app/state/session.ts")
        content = session_path.read_text()
        
        assert "function createSessionFromAPIKey" in content
        assert "apiKey: string" in content
        assert "roles: string[]" in content
    
    def test_update_session_activity_exists(self):
        """Verify updateSessionActivity function exists."""
        session_path = Path("/workspace/app/state/session.ts")
        content = session_path.read_text()
        
        assert "function updateSessionActivity" in content
        assert "lastActivityAt" in content
    
    def test_is_session_valid_exists(self):
        """Verify isSessionValid function exists."""
        session_path = Path("/workspace/app/state/session.ts")
        content = session_path.read_text()
        
        assert "function isSessionValid" in content
        assert "session: UserSession" in content
    
    def test_is_session_valid_checks_expiration(self):
        """Verify isSessionValid checks token expiration."""
        session_path = Path("/workspace/app/state/session.ts")
        content = session_path.read_text()
        
        # Find function
        start = content.find("function isSessionValid")
        end = content.find("\n}", start)
        func_block = content[start:end]
        
        # Should check JWT expiration for token-based sessions
        assert "isJWTExpired" in func_block or "parseJWT" in func_block
    
    def test_refresh_session_exists(self):
        """Verify refreshSession function exists."""
        session_path = Path("/workspace/app/state/session.ts")
        content = session_path.read_text()
        
        assert "function refreshSession" in content


class TestSessionStorage:
    """Test browser storage integration."""
    
    def test_save_session_exists(self):
        """Verify saveSession function exists."""
        session_path = Path("/workspace/app/state/session.ts")
        content = session_path.read_text()
        
        assert "function saveSession" in content
        assert "localStorage" in content
    
    def test_load_session_exists(self):
        """Verify loadSession function exists."""
        session_path = Path("/workspace/app/state/session.ts")
        content = session_path.read_text()
        
        assert "function loadSession" in content
        assert "localStorage" in content
    
    def test_clear_session_exists(self):
        """Verify clearSession function exists."""
        session_path = Path("/workspace/app/state/session.ts")
        content = session_path.read_text()
        
        assert "function clearSession" in content
        assert "localStorage" in content
    
    def test_storage_key_defined(self):
        """Verify storage key constant is defined."""
        session_path = Path("/workspace/app/state/session.ts")
        content = session_path.read_text()
        
        assert "SESSION_STORAGE_KEY" in content
    
    def test_save_session_handles_errors(self):
        """Verify saveSession handles storage errors gracefully."""
        session_path = Path("/workspace/app/state/session.ts")
        content = session_path.read_text()
        
        # Find saveSession function
        start = content.find("function saveSession")
        end = content.find("\n}", start)
        func_block = content[start:end]
        
        # Should have error handling
        assert "try" in func_block
        assert "catch" in func_block


class TestSessionImports:
    """Test required imports from other modules."""
    
    def test_imports_role_definitions(self):
        """Verify session.ts imports from roles.ts."""
        session_path = Path("/workspace/app/state/session.ts")
        content = session_path.read_text()
        
        # Should import from roles module
        assert "from '../lib/roles'" in content
        
        # Should import role constants
        assert "ROLE_GENERAL" in content
        assert "hasCapability" in content or "getAggregateCapabilities" in content
    
    def test_imports_feature_flags(self):
        """Verify session.ts imports from flags.ts."""
        session_path = Path("/workspace/app/state/session.ts")
        content = session_path.read_text()
        
        # Should import from flags module
        assert "from '../config/flags'" in content
        
        # Should import UIFlags type
        assert "UIFlags" in content


class TestSessionAcceptanceCriteria:
    """Verify acceptance criteria for session management."""
    
    def test_logged_in_user_gets_role_from_jwt(self):
        """
        Acceptance: Logged-in user has role resolved from JWT.
        """
        session_path = Path("/workspace/app/state/session.ts")
        content = session_path.read_text()
        
        # Should parse JWT and extract roles
        assert "parseJWT" in content
        assert "getUserRole" in content or "getUserRoles" in content
        
        # Should create authenticated session
        assert "isAuthenticated: true" in content
    
    def test_anonymous_user_gets_general_role(self):
        """
        Acceptance: Anonymous user gets 'general' role.
        """
        session_path = Path("/workspace/app/state/session.ts")
        content = session_path.read_text()
        
        # Find ANONYMOUS_SESSION
        start = content.find("ANONYMOUS_SESSION")
        end = content.find("};", start)
        anonymous_block = content[start:end]
        
        assert "ROLE_GENERAL" in anonymous_block
        assert "isAnonymous: true" in anonymous_block
    
    def test_ui_flags_resolved_from_capabilities(self):
        """
        Acceptance: UI flags are computed from user capabilities.
        """
        session_path = Path("/workspace/app/state/session.ts")
        content = session_path.read_text()
        
        # Should compute flags based on capabilities
        assert "resolveUIFlagsForRoles" in content
        assert "getAggregateCapabilities" in content or "capabilities" in content
        
        # Should check specific capabilities
        assert "CAP_READ_LEDGER_FULL" in content
        assert "CAP_VIEW_DEBUG" in content


class TestExportsAndIntegration:
    """Test module exports and integration points."""
    
    def test_default_export_exists(self):
        """Verify default export with all functions."""
        session_path = Path("/workspace/app/state/session.ts")
        content = session_path.read_text()
        
        # Find default export
        assert "export default" in content
        
        # Should export key functions
        export_start = content.find("export default")
        export_end = content.find("}", export_start)
        export_block = content[export_start:export_end]
        
        assert "getUserRole" in export_block
        assert "createSessionFromJWT" in export_block
        assert "saveSession" in export_block
        assert "loadSession" in export_block
