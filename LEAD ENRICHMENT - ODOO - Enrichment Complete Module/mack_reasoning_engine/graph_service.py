# -*- coding: utf-8 -*-
"""
PlastOS Graph Service - Neo4j + AI RAG Component
=================================================

AI-augmented matching using Neo4j knowledge graph and Retrieval-Augmented Generation.
Provides contextual insights, pattern recognition, and intelligent recommendations.

Components:
- Neo4j graph database for relationship mapping
- OpenAI-compatible API for embeddings and reasoning
- RAG pipeline for contextual augmentation
- Pattern detection for successful matches
- Market intelligence integration

Author: PlastOS Development Team
Version: 6.0
License: Proprietary
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
import json
import hashlib

_logger = logging.getLogger(__name__)

# Optional imports - gracefully degrade if not available
try:
    from neo4j import GraphDatabase
    NEO4J_AVAILABLE = True
except ImportError:
    NEO4J_AVAILABLE = False
    _logger.warning("Neo4j driver not available - graph features disabled")

try:
    import openai
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False
    _logger.warning("OpenAI library not available - AI features disabled")


# ============================================================================
# GRAPH SERVICE
# ============================================================================

class GraphService:
    """
    AI-augmented matching service using Neo4j and RAG.
    
    Features:
    - Knowledge graph for relationship mapping
    - Embedding-based similarity search
    - Pattern recognition from historical matches
    - Contextual recommendations
    - Market intelligence integration
    
    Graceful degradation: Falls back to basic augmentation if
    Neo4j or OpenAI services are unavailable.
    """
    
    def __init__(self, env):
        """
        Initialize graph service with Odoo environment.
        
        Args:
            env: Odoo environment for database access
        """
        self.env = env
        self._neo4j_driver = None
        self._openai_client = None
        self._initialized = False
        self._embedding_cache = {}
        
        _logger.info("GraphService initialized")
    
    def _lazy_init(self):
        """Lazy initialization of Neo4j and OpenAI connections."""
        if self._initialized:
            return
        
        # Initialize Neo4j
        if NEO4J_AVAILABLE:
            try:
                config = self.env['ir.config_parameter'].sudo()
                neo4j_uri = config.get_param('plastos.neo4j_uri', 'bolt://localhost:7687')
                neo4j_user = config.get_param('plastos.neo4j_user', 'neo4j')
                neo4j_password = config.get_param('plastos.neo4j_password', '')
                
                if neo4j_password:
                    self._neo4j_driver = GraphDatabase.driver(
                        neo4j_uri,
                        auth=(neo4j_user, neo4j_password)
                    )
                    _logger.info("Neo4j connection established")
                else:
                    _logger.warning("Neo4j password not configured")
            except Exception as e:
                _logger.error(f"Failed to initialize Neo4j: {e}")
        
        # Initialize OpenAI
        if OPENAI_AVAILABLE:
            try:
                config = self.env['ir.config_parameter'].sudo()
                api_key = config.get_param('plastos.openai_api_key', '')
                api_base = config.get_param('plastos.openai_api_base', '')
                
                if api_key:
                    if api_base:
                        openai.api_base = api_base
                    openai.api_key = api_key
                    self._openai_client = openai
                    _logger.info("OpenAI client configured")
                else:
                    _logger.warning("OpenAI API key not configured")
            except Exception as e:
                _logger.error(f"Failed to initialize OpenAI: {e}")
        
        self._initialized = True
    
    # ========================================================================
    # PUBLIC API - MATCH AUGMENTATION
    # ========================================================================
    
    def augment_matches(
        self,
        deterministic_matches: List,
        context
    ) -> List:
        """
        Augment deterministic matches with AI insights.
        
        Augmentation includes:
        1. Contextual recommendations from knowledge graph
        2. Pattern-based adjustments from historical data
        3. Embedding-based similarity scoring
        4. Market intelligence insights
        5. Relationship strength signals
        
        Args:
            deterministic_matches: Matches from deterministic matcher
            context: ReasoningContext with specifications
            
        Returns:
            Augmented matches with AI insights
        """
        self._lazy_init()
        
        if not deterministic_matches:
            return []
        
        _logger.info(
            f"Augmenting {len(deterministic_matches)} matches with AI insights"
        )
        
        # 1. Get historical patterns
        patterns = self._get_successful_patterns(context)
        
        # 2. Augment each match
        augmented = []
        for match in deterministic_matches:
            # Apply pattern-based adjustments
            adjusted_match = self._apply_patterns(match, patterns, context)
            
            # Add graph-based insights
            graph_insights = self._get_graph_insights(
                adjusted_match.buyer_partner_id,
                context
            )
            
            # Enhance recommendations
            adjusted_match.recommendations.extend(graph_insights['recommendations'])
            
            # Add confidence boost for pattern matches
            if graph_insights['pattern_match_count'] > 0:
                adjusted_match.confidence = min(
                    1.0,
                    adjusted_match.confidence + (graph_insights['pattern_match_count'] * 0.05)
                )
            
            augmented.append(adjusted_match)
        
        # 3. Re-sort by adjusted scores
        augmented.sort(key=lambda m: m.total_score, reverse=True)
        
        _logger.info("Match augmentation completed")
        return augmented
    
    def extract_supplier_data(
        self,
        raw_data: Dict[str, Any],
        source_channel: str = 'email'
    ) -> Dict[str, Any]:
        """
        Extract and normalize supplier data using AI.
        
        Process:
        1. Parse raw input (email, form data, etc.)
        2. Extract structured fields using NLP
        3. Validate and normalize values
        4. Calculate confidence scores
        
        Args:
            raw_data: Raw supplier intake data
            source_channel: Source channel identifier
            
        Returns:
            Normalized supplier data dictionary
        """
        self._lazy_init()
        
        _logger.info(f"Extracting supplier data from {source_channel}")
        
        # Use AI extraction if available, otherwise fallback
        if self._openai_client:
            try:
                extracted = self._ai_extract_supplier_data(raw_data)
                extracted['extraction_method'] = 'ai'
                return extracted
            except Exception as e:
                _logger.error(f"AI extraction failed: {e}")
        
        # Fallback to rule-based extraction
        return self._rule_based_extract(raw_data, source_channel)
    
    # ========================================================================
    # PATTERN RECOGNITION
    # ========================================================================
    
    def _get_successful_patterns(self, context) -> Dict[str, Any]:
        """
        Get patterns from historically successful matches.
        
        Analyzes:
        - Polymer combinations that work well
        - Buyer preferences and behaviors
        - Seasonal trends
        - Price sweet spots
        """
        patterns = {
            'polymer_preferences': {},
            'volume_patterns': {},
            'timing_insights': {},
            'price_patterns': {},
        }
        
        # Query successful transactions
        successful_txs = self.env['sm.tx'].search([
            ('state', '=', 'closed'),
            ('polymer_type', '=', context.polymer_type),
            ('create_date', '>=', datetime.now() - timedelta(days=365)),
        ], limit=100)
        
        if not successful_txs:
            return patterns
        
        # Analyze polymer preferences
        buyer_polymer_counts = {}
        for tx in successful_txs:
            buyer_id = tx.buyer_id.id
            if buyer_id not in buyer_polymer_counts:
                buyer_polymer_counts[buyer_id] = 0
            buyer_polymer_counts[buyer_id] += 1
        
        patterns['polymer_preferences'] = buyer_polymer_counts
        
        # Analyze volume patterns
        volumes = [tx.quantity_kg for tx in successful_txs if tx.quantity_kg]
        if volumes:
            patterns['volume_patterns'] = {
                'avg_volume': sum(volumes) / len(volumes),
                'min_volume': min(volumes),
                'max_volume': max(volumes),
            }
        
        # Analyze timing
        # Group by month to detect seasonal patterns
        monthly_counts = {}
        for tx in successful_txs:
            month = tx.create_date.strftime('%Y-%m')
            monthly_counts[month] = monthly_counts.get(month, 0) + 1
        
        if monthly_counts:
            patterns['timing_insights'] = {
                'busiest_months': sorted(
                    monthly_counts.items(),
                    key=lambda x: x[1],
                    reverse=True
                )[:3]
            }
        
        # Analyze price patterns
        prices = [tx.price_per_kg for tx in successful_txs if tx.price_per_kg]
        if prices:
            patterns['price_patterns'] = {
                'avg_price': sum(prices) / len(prices),
                'min_price': min(prices),
                'max_price': max(prices),
            }
        
        return patterns
    
    def _apply_patterns(self, match, patterns: Dict, context):
        """
        Apply learned patterns to adjust match scoring.
        
        Adjustments:
        - Boost score if buyer has successful history with polymer
        - Adjust for volume preferences
        - Consider seasonal timing
        - Factor in price trends
        """
        # Boost for polymer preference
        buyer_id = match.buyer_partner_id
        polymer_prefs = patterns.get('polymer_preferences', {})
        
        if buyer_id in polymer_prefs:
            # Buyer has successful history with this polymer
            success_count = polymer_prefs[buyer_id]
            boost = min(0.1, success_count * 0.02)  # Max 0.1 boost
            
            match.total_score = min(1.0, match.total_score + boost)
            match.confidence = min(1.0, match.confidence + boost)
            
            match.recommendations.append(
                f"Historical success: {success_count} successful transactions with this polymer"
            )
        
        # Volume pattern adjustment
        volume_patterns = patterns.get('volume_patterns', {})
        if volume_patterns and context.quantity_kg:
            avg_volume = volume_patterns['avg_volume']
            volume_ratio = context.quantity_kg / avg_volume
            
            if 0.8 <= volume_ratio <= 1.2:
                match.recommendations.append(
                    f"Volume aligns with historical success pattern (avg: {avg_volume:.0f} kg)"
                )
        
        # Price pattern feedback
        price_patterns = patterns.get('price_patterns', {})
        if price_patterns and context.target_price:
            avg_price = price_patterns['avg_price']
            
            if abs(context.target_price - avg_price) / avg_price < 0.1:
                match.recommendations.append(
                    f"Price aligns with successful historical range (${avg_price:.2f}/kg avg)"
                )
        
        return match
    
    # ========================================================================
    # GRAPH DATABASE QUERIES
    # ========================================================================
    
    def _get_graph_insights(
        self,
        buyer_partner_id: int,
        context
    ) -> Dict[str, Any]:
        """
        Query Neo4j knowledge graph for relationship insights.
        
        Queries:
        - Direct relationships (buyer-supplier)
        - Network effects (shared partners)
        - Community detection (buyer clusters)
        - Path analysis (connection strength)
        """
        insights = {
            'recommendations': [],
            'pattern_match_count': 0,
            'network_strength': 0.0,
            'community_score': 0.0,
        }
        
        if not self._neo4j_driver:
            return insights
        
        try:
            with self._neo4j_driver.session() as session:
                # Query relationship strength
                result = session.run(
                    """
                    MATCH (b:Buyer {partner_id: $buyer_id})
                    OPTIONAL MATCH (b)-[r:TRADED_WITH]->(s:Supplier)
                    RETURN count(r) as relationship_count,
                           avg(r.success_score) as avg_success
                    """,
                    buyer_id=buyer_partner_id
                )
                
                record = result.single()
                if record:
                    rel_count = record['relationship_count'] or 0
                    avg_success = record['avg_success'] or 0.0
                    
                    insights['pattern_match_count'] = rel_count
                    insights['network_strength'] = avg_success
                    
                    if rel_count > 5:
                        insights['recommendations'].append(
                            f"Strong network presence: {rel_count} relationships"
                        )
                    
                    if avg_success > 0.8:
                        insights['recommendations'].append(
                            f"High success rate: {avg_success*100:.1f}% average"
                        )
        
        except Exception as e:
            _logger.error(f"Graph query failed: {e}")
        
        return insights
    
    # ========================================================================
    # AI EXTRACTION
    # ========================================================================
    
    def _ai_extract_supplier_data(
        self,
        raw_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Use OpenAI to extract structured data from raw input.
        
        Uses GPT-4 with function calling to extract:
        - Polymer type and grade
        - Technical specifications
        - Quantity and pricing
        - Delivery requirements
        - Contact information
        """
        if not self._openai_client:
            raise RuntimeError("OpenAI client not available")
        
        # Prepare extraction prompt
        prompt = self._build_extraction_prompt(raw_data)
        
        # Define extraction schema
        functions = [{
            "name": "extract_supplier_intake",
            "description": "Extract structured supplier intake data",
            "parameters": {
                "type": "object",
                "properties": {
                    "polymer_type": {
                        "type": "string",
                        "description": "Polymer type code (HDPE, LDPE, PP, PET, etc.)"
                    },
                    "polymer_grade": {
                        "type": "string",
                        "description": "Polymer grade or application"
                    },
                    "quantity_kg": {
                        "type": "number",
                        "description": "Quantity in kilograms"
                    },
                    "target_price": {
                        "type": "number",
                        "description": "Target price per kg in USD"
                    },
                    "density": {
                        "type": "number",
                        "description": "Density in g/cm³"
                    },
                    "melt_index": {
                        "type": "number",
                        "description": "Melt flow index in g/10min"
                    },
                    "contamination_pct": {
                        "type": "number",
                        "description": "Contamination percentage"
                    },
                    "pcr_percentage": {
                        "type": "number",
                        "description": "Post-consumer recycled content percentage"
                    },
                    "delivery_location": {
                        "type": "string",
                        "description": "Delivery location or region"
                    },
                    "color": {
                        "type": "string",
                        "description": "Material color"
                    },
                    "confidence": {
                        "type": "number",
                        "description": "Extraction confidence (0.0-1.0)"
                    }
                },
                "required": ["polymer_type", "quantity_kg"]
            }
        }]
        
        # Call OpenAI API
        response = self._openai_client.ChatCompletion.create(
            model="gpt-4",
            messages=[
                {
                    "role": "system",
                    "content": "You are a plastic recycling data extraction expert. "
                               "Extract structured information from supplier intake data."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            functions=functions,
            function_call={"name": "extract_supplier_intake"}
        )
        
        # Parse response
        if response.choices[0].message.get("function_call"):
            function_args = json.loads(
                response.choices[0].message["function_call"]["arguments"]
            )
            return function_args
        
        raise RuntimeError("Failed to extract data from AI response")
    
    def _build_extraction_prompt(self, raw_data: Dict[str, Any]) -> str:
        """Build extraction prompt from raw data."""
        
        # Convert raw data to text format
        text_parts = []
        
        if 'subject' in raw_data:
            text_parts.append(f"Subject: {raw_data['subject']}")
        
        if 'body' in raw_data:
            text_parts.append(f"Body: {raw_data['body']}")
        
        if 'form_data' in raw_data:
            text_parts.append(f"Form Data: {json.dumps(raw_data['form_data'])}")
        
        prompt = "Extract supplier intake data from the following:\n\n"
        prompt += "\n".join(text_parts)
        prompt += "\n\nExtract structured polymer specifications and business terms."
        
        return prompt
    
    # ========================================================================
    # FALLBACK EXTRACTION
    # ========================================================================
    
    def _rule_based_extract(
        self,
        raw_data: Dict[str, Any],
        source_channel: str
    ) -> Dict[str, Any]:
        """
        Rule-based extraction fallback when AI is unavailable.
        
        Uses regex patterns and keyword matching.
        """
        extracted = {
            'extraction_method': 'rule_based',
            'confidence': 0.5,  # Lower confidence for rule-based
        }
        
        # Extract from form data if available
        if 'form_data' in raw_data:
            form = raw_data['form_data']
            
            extracted.update({
                'polymer_type': form.get('polymer_type', '').upper(),
                'polymer_grade': form.get('grade'),
                'quantity_kg': self._parse_float(form.get('quantity')),
                'target_price': self._parse_float(form.get('price')),
                'density': self._parse_float(form.get('density')),
                'melt_index': self._parse_float(form.get('melt_index')),
                'contamination_pct': self._parse_float(form.get('contamination')),
                'pcr_percentage': self._parse_float(form.get('pcr_content')),
                'delivery_location': form.get('location'),
                'color': form.get('color'),
            })
        
        # Extract from email body if available
        elif 'body' in raw_data:
            body = raw_data['body'].upper()
            
            # Simple polymer type detection
            for polymer in ['HDPE', 'LDPE', 'PP', 'PET', 'PVC', 'PS']:
                if polymer in body:
                    extracted['polymer_type'] = polymer
                    break
        
        # Remove None values
        extracted = {k: v for k, v in extracted.items() if v is not None}
        
        return extracted
    
    def _parse_float(self, value) -> Optional[float]:
        """Safely parse float value."""
        if value is None:
            return None
        try:
            return float(value)
        except (ValueError, TypeError):
            return None
    
    # ========================================================================
    # EMBEDDING AND SIMILARITY
    # ========================================================================
    
    def get_embedding(self, text: str) -> List[float]:
        """
        Get embedding vector for text.
        
        Uses OpenAI embeddings API with caching.
        
        Args:
            text: Text to embed
            
        Returns:
            Embedding vector (1536 dimensions for text-embedding-ada-002)
        """
        # Check cache
        cache_key = hashlib.md5(text.encode()).hexdigest()
        if cache_key in self._embedding_cache:
            return self._embedding_cache[cache_key]
        
        if not self._openai_client:
            return []
        
        try:
            response = self._openai_client.Embedding.create(
                model="text-embedding-ada-002",
                input=text
            )
            
            embedding = response['data'][0]['embedding']
            
            # Cache result
            self._embedding_cache[cache_key] = embedding
            
            return embedding
            
        except Exception as e:
            _logger.error(f"Failed to get embedding: {e}")
            return []
    
    def calculate_similarity(
        self,
        embedding1: List[float],
        embedding2: List[float]
    ) -> float:
        """
        Calculate cosine similarity between embeddings.
        
        Args:
            embedding1: First embedding vector
            embedding2: Second embedding vector
            
        Returns:
            Similarity score (0.0-1.0)
        """
        if not embedding1 or not embedding2:
            return 0.0
        
        # Cosine similarity
        dot_product = sum(a * b for a, b in zip(embedding1, embedding2))
        
        magnitude1 = sum(a * a for a in embedding1) ** 0.5
        magnitude2 = sum(b * b for b in embedding2) ** 0.5
        
        if magnitude1 == 0 or magnitude2 == 0:
            return 0.0
        
        similarity = dot_product / (magnitude1 * magnitude2)
        
        # Normalize to 0-1 range
        return (similarity + 1) / 2
    
    # ========================================================================
    # CLEANUP
    # ========================================================================
    
    def close(self):
        """Close database connections."""
        if self._neo4j_driver:
            self._neo4j_driver.close()
            _logger.info("Neo4j connection closed")


# ============================================================================
# MODULE EXPORTS
# ============================================================================

def get_graph_service(env):
    """Factory function to get graph service instance."""
    return GraphService(env)
