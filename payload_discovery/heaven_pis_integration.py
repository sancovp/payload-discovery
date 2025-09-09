"""
HEAVEN PIS Integration for PayloadDiscovery.

Maps PayloadDiscovery systems to PromptInjectionSystemVX1 and provides
a state machine that can servo them based on DiscoveryReceipt.
"""

import logging
from typing import List, Optional, Dict, Any
from pathlib import Path
from pydantic import BaseModel, Field

from .core import PayloadDiscovery, PayloadDiscoveryPiece

logger = logging.getLogger(__name__)

# Import HEAVEN PIS components
try:
    from heaven_base.tool_utils.prompt_injection_system_vX1 import (
        PromptInjectionSystemVX1,
        PromptInjectionSystemConfigVX1,
        PromptStepDefinitionVX1,
        PromptBlockDefinitionVX1,
        BlockTypeVX1
    )
    from heaven_base.baseheavenagent import HeavenAgentConfig
except ImportError as e:
    logger.warning(f"HEAVEN not available, using stubs: {e}", exc_info=True)
    # Create stubs if HEAVEN not available for development
    class BlockTypeVX1:
        FREESTYLE = "freestyle"
        REFERENCE = "reference"
    
    class PromptBlockDefinitionVX1(BaseModel):
        type: str
        content: str
    
    class PromptStepDefinitionVX1(BaseModel):
        name: Optional[str] = None
        blocks: List[PromptBlockDefinitionVX1]
    
    class HeavenAgentConfig(BaseModel):
        system_prompt: str = ""
        prompt_suffix_blocks: Optional[List[str]] = None
    
    class PromptInjectionSystemConfigVX1(BaseModel):
        steps: List[PromptStepDefinitionVX1]
        template_vars: Dict[str, Any]
        agent_config: HeavenAgentConfig
    
    class PromptInjectionSystemVX1:
        def __init__(self, config: PromptInjectionSystemConfigVX1):
            self.config = config
            self.current_step_index = 0
        
        def get_next_prompt(self) -> Optional[str]:
            if self.current_step_index >= len(self.config.steps):
                return None
            step = self.config.steps[self.current_step_index]
            self.current_step_index += 1
            return "".join([b.content for b in step.blocks])
        
        def has_next_prompt(self) -> bool:
            return self.current_step_index < len(self.config.steps)
        
        def reset_sequence(self):
            self.current_step_index = 0


class DiscoveryReceipt(BaseModel):
    """
    Tracks agent progress through a PayloadDiscovery system.
    
    The receipt records which pieces have been consumed and allows
    the state machine to resume from where it left off.
    """
    
    domain: str = Field(..., description="Domain of the PayloadDiscovery system")
    version: str = Field(..., description="Version of the PayloadDiscovery system")
    completed_pieces: List[int] = Field(
        default_factory=list,
        description="Sequence numbers of completed pieces"
    )
    current_directory: Optional[str] = Field(
        default=None,
        description="Current directory being processed"
    )
    current_piece_index: int = Field(
        default=0,
        description="Index of current piece in current directory"
    )
    total_pieces: int = Field(
        default=0,
        description="Total number of pieces in the system"
    )
    
    def is_complete(self) -> bool:
        """Check if all pieces have been consumed."""
        return len(self.completed_pieces) >= self.total_pieces
    
    def mark_piece_complete(self, sequence_number: int):
        """Mark a piece as completed."""
        if sequence_number not in self.completed_pieces:
            self.completed_pieces.append(sequence_number)
    
    def get_completion_percentage(self) -> float:
        """Get percentage of pieces completed."""
        if self.total_pieces == 0:
            return 0.0
        return (len(self.completed_pieces) / self.total_pieces) * 100


class PayloadDiscoveryPISMapper:
    """
    Maps PayloadDiscovery systems to PromptInjectionSystemVX1.
    
    This class converts the numbered instruction files from a PayloadDiscovery
    into a sequence of prompt steps that can be consumed by HEAVEN PIS.
    """
    
    def __init__(self, payload_discovery: PayloadDiscovery):
        self.payload_discovery = payload_discovery
        logger.debug(f"Initialized mapper for {payload_discovery.domain} {payload_discovery.version}")
    
    def _piece_to_prompt_step(self, piece: PayloadDiscoveryPiece) -> PromptStepDefinitionVX1:
        """Convert a PayloadDiscoveryPiece to a PromptStepDefinition."""
        # Create a FREESTYLE block with the piece content
        block = PromptBlockDefinitionVX1(
            type=BlockTypeVX1.FREESTYLE,
            content=piece.content
        )
        
        # Create step with name from piece title
        return PromptStepDefinitionVX1(
            name=f"{piece.filename}: {piece.title}",
            blocks=[block]
        )
    
    def _get_ordered_pieces(self) -> List[PayloadDiscoveryPiece]:
        """Get all pieces in traversal order."""
        ordered_pieces = []
        
        # Add root files first (usually README, ARCHITECTURE)
        ordered_pieces.extend(
            sorted(self.payload_discovery.root_files, 
                   key=lambda p: p.sequence_number)
        )
        
        # Add directory pieces in directory order
        for dirname in sorted(self.payload_discovery.directories.keys()):
            pieces = self.payload_discovery.directories[dirname]
            ordered_pieces.extend(
                sorted(pieces, key=lambda p: p.sequence_number)
            )
        
        return ordered_pieces
    
    def to_pis_config(
        self,
        template_vars: Optional[Dict[str, Any]] = None,
        agent_config: Optional[HeavenAgentConfig] = None
    ) -> PromptInjectionSystemConfigVX1:
        """
        Convert PayloadDiscovery to PromptInjectionSystemConfigVX1.
        
        Args:
            template_vars: Variables for FREESTYLE template substitution
            agent_config: HeavenAgentConfig for REFERENCE resolution
            
        Returns:
            PromptInjectionSystemConfigVX1 ready for PIS consumption
        """
        # Get all pieces in order
        ordered_pieces = self._get_ordered_pieces()
        
        # Convert each piece to a prompt step
        steps = [self._piece_to_prompt_step(piece) for piece in ordered_pieces]
        
        # Create PIS config
        return PromptInjectionSystemConfigVX1(
            steps=steps,
            template_vars=template_vars or {},
            agent_config=agent_config or HeavenAgentConfig()
        )
    
    def create_pis(
        self,
        template_vars: Optional[Dict[str, Any]] = None,
        agent_config: Optional[HeavenAgentConfig] = None
    ) -> PromptInjectionSystemVX1:
        """
        Create a PromptInjectionSystemVX1 from the PayloadDiscovery.
        
        Returns:
            PromptInjectionSystemVX1 ready to servo prompts
        """
        config = self.to_pis_config(template_vars, agent_config)
        return PromptInjectionSystemVX1(config)


class PayloadDiscoveryStateMachine:
    """
    State machine that servos PayloadDiscovery through PIS based on DiscoveryReceipt.
    
    This allows resumable, stateful traversal of PayloadDiscovery systems.
    """
    
    def __init__(
        self,
        payload_discovery: PayloadDiscovery,
        receipt: Optional[DiscoveryReceipt] = None,
        template_vars: Optional[Dict[str, Any]] = None,
        agent_config: Optional[HeavenAgentConfig] = None
    ):
        self.payload_discovery = payload_discovery
        self.mapper = PayloadDiscoveryPISMapper(payload_discovery)
        
        # Initialize or use provided receipt
        if receipt is None:
            # Count total pieces
            total = len(payload_discovery.root_files)
            for pieces in payload_discovery.directories.values():
                total += len(pieces)
            
            self.receipt = DiscoveryReceipt(
                domain=payload_discovery.domain,
                version=payload_discovery.version,
                total_pieces=total
            )
        else:
            self.receipt = receipt
        
        # Create PIS
        self.pis = self.mapper.create_pis(template_vars, agent_config)
        
        # Fast-forward PIS to match receipt state
        self._sync_pis_to_receipt()
        
        logger.info(f"Initialized state machine at {self.receipt.get_completion_percentage():.1f}% complete")
    
    def _sync_pis_to_receipt(self):
        """Sync PIS position to match receipt state."""
        # Reset PIS to beginning
        self.pis.reset_sequence()
        
        # Fast-forward through completed pieces
        completed_count = len(self.receipt.completed_pieces)
        for _ in range(completed_count):
            if self.pis.has_next_prompt():
                self.pis.get_next_prompt()
    
    def get_next_prompt(self) -> Optional[str]:
        """
        Get the next prompt from the PayloadDiscovery sequence.
        
        Returns:
            Next prompt string or None if complete
        """
        if self.receipt.is_complete():
            return None
        
        prompt = self.pis.get_next_prompt()
        if prompt:
            # Mark the piece as complete
            # Note: We're tracking by position, need to map back to sequence number
            ordered_pieces = self.mapper._get_ordered_pieces()
            current_index = len(self.receipt.completed_pieces)
            if current_index < len(ordered_pieces):
                piece = ordered_pieces[current_index]
                self.receipt.mark_piece_complete(piece.sequence_number)
                logger.debug(f"Completed piece {piece.sequence_number}: {piece.filename}")
        
        return prompt
    
    def has_next_prompt(self) -> bool:
        """Check if there are more prompts to process."""
        return self.pis.has_next_prompt()
    
    def reset(self):
        """Reset to beginning of sequence."""
        self.receipt = DiscoveryReceipt(
            domain=self.payload_discovery.domain,
            version=self.payload_discovery.version,
            total_pieces=self.receipt.total_pieces
        )
        self.pis.reset_sequence()
    
    def get_receipt(self) -> DiscoveryReceipt:
        """Get current receipt for persistence."""
        return self.receipt
    
    def get_progress_summary(self) -> str:
        """Get human-readable progress summary."""
        percentage = self.receipt.get_completion_percentage()
        completed = len(self.receipt.completed_pieces)
        total = self.receipt.total_pieces
        
        return (
            f"PayloadDiscovery: {self.payload_discovery.domain} {self.payload_discovery.version}\n"
            f"Progress: {completed}/{total} pieces ({percentage:.1f}% complete)"
        )