"""
Sovereign Cognitive Engine - Graph Analytics
=============================================
Community detection and graph analysis using Neo4j GDS.
"""

import logging
from typing import Optional

from neo4j import AsyncGraphDatabase, AsyncDriver
from neo4j.exceptions import Neo4jError

from config import Settings, get_settings

logger = logging.getLogger(__name__)


class GraphAnalytics:
    """
    Graph analytics using Neo4j Graph Data Science (GDS) library.
    
    Provides community detection and graph algorithms for knowledge organization.
    
    Prerequisites:
        - Neo4j GDS plugin installed (included in neo4j:*-community images with APOC)
        - Sufficient memory for in-memory graph projections
    
    Example:
        ```python
        async with GraphAnalytics() as analytics:
            stats = await analytics.run_leiden_community_detection()
        ```
    """
    
    def __init__(self, settings: Optional[Settings] = None):
        """Initialize analytics with configuration."""
        self.settings = settings or get_settings()
        self._neo4j_driver: Optional[AsyncDriver] = None
    
    async def __aenter__(self):
        """Async context manager entry."""
        self._neo4j_driver = AsyncGraphDatabase.driver(
            self.settings.neo4j_uri,
            auth=(self.settings.neo4j_user, self.settings.neo4j_password),
        )
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self._neo4j_driver:
            await self._neo4j_driver.close()
    
    async def run_leiden_community_detection(
        self,
        graph_name: str = "entity_graph",
        write_property: str = "community_id",
        max_levels: int = 10,
        gamma: float = 1.0,
        theta: float = 0.01,
    ) -> dict:
        """
        Run Leiden community detection algorithm on the entity graph.
        
        The Leiden algorithm finds densely connected communities of entities,
        enabling "Deep Dive" features by grouping related knowledge.
        
        Cypher Query Explanation:
        1. Project in-memory graph with Entity nodes and RELATED_TO edges
        2. Run gds.leiden.write() to detect communities
        3. Write community_id property back to Entity nodes
        4. Drop projected graph to free memory
        
        Args:
            graph_name: Name for the in-memory GDS projection
            write_property: Property name to store community ID on nodes
            max_levels: Maximum Leiden iteration levels
            gamma: Resolution parameter (higher = smaller communities)
            theta: Theta parameter for refinement phase
            
        Returns:
            Dict with statistics: community_count, node_count, modularity
            
        Raises:
            Neo4jError: If GDS plugin is not available or query fails
            
        Note:
            Requires Neo4j GDS plugin. Install with:
            NEO4J_PLUGINS='["graph-data-science"]' in compose.yaml
        """
        if not self._neo4j_driver:
            raise RuntimeError("Neo4j driver not initialized. Use async context manager.")
        
        async with self._neo4j_driver.session() as session:
            try:
                # Step 1: Create in-memory graph projection
                # This projects Entity nodes and RELATED_TO relationships into GDS
                logger.info(f"Creating graph projection: {graph_name}")
                
                await session.run(
                    """
                    // Drop existing projection if present
                    CALL gds.graph.drop($graph_name, false)
                    YIELD graphName
                    RETURN graphName
                    """,
                    graph_name=graph_name,
                )
                
                await session.run(
                    """
                    // Create native projection of Entity nodes and relationships
                    CALL gds.graph.project(
                        $graph_name,
                        'Entity',
                        {
                            RELATED_TO: {
                                type: 'RELATED_TO',
                                orientation: 'UNDIRECTED',
                                properties: ['weight']
                            }
                        }
                    )
                    YIELD graphName, nodeCount, relationshipCount
                    RETURN graphName, nodeCount, relationshipCount
                    """,
                    graph_name=graph_name,
                )
                
                # Step 2: Run Leiden community detection
                logger.info("Running Leiden community detection...")
                
                result = await session.run(
                    """
                    // Execute Leiden algorithm and write results back
                    CALL gds.leiden.write($graph_name, {
                        writeProperty: $write_property,
                        maxLevels: $max_levels,
                        gamma: $gamma,
                        theta: $theta,
                        includeIntermediateCommunities: false
                    })
                    YIELD communityCount, nodePropertiesWritten, modularity, 
                          ranLevels, didConverge, preProcessingMillis, 
                          computeMillis, writeMillis
                    RETURN communityCount, nodePropertiesWritten, modularity,
                           ranLevels, didConverge,
                           preProcessingMillis + computeMillis + writeMillis AS totalMillis
                    """,
                    graph_name=graph_name,
                    write_property=write_property,
                    max_levels=max_levels,
                    gamma=gamma,
                    theta=theta,
                )
                
                record = await result.single()
                stats = {
                    "community_count": record["communityCount"],
                    "node_count": record["nodePropertiesWritten"],
                    "modularity": record["modularity"],
                    "levels_ran": record["ranLevels"],
                    "converged": record["didConverge"],
                    "total_time_ms": record["totalMillis"],
                }
                
                logger.info(
                    f"Leiden complete: {stats['community_count']} communities, "
                    f"modularity={stats['modularity']:.4f}"
                )
                
                # Step 3: Cleanup - drop the in-memory projection
                await session.run(
                    """
                    CALL gds.graph.drop($graph_name)
                    YIELD graphName
                    RETURN graphName
                    """,
                    graph_name=graph_name,
                )
                
                return stats
                
            except Neo4jError as e:
                if "Unknown procedure" in str(e):
                    logger.error(
                        "Neo4j GDS plugin not installed. "
                        "Add NEO4J_PLUGINS='[\"graph-data-science\"]' to compose.yaml"
                    )
                raise
    
    async def get_community_summary(self, community_id: int) -> dict:
        """
        Get summary statistics for a specific community.
        
        Args:
            community_id: Community ID assigned by Leiden
            
        Returns:
            Dict with entity count, top entities, relationship count
        """
        if not self._neo4j_driver:
            raise RuntimeError("Neo4j driver not initialized. Use async context manager.")
        
        async with self._neo4j_driver.session() as session:
            result = await session.run(
                """
                // Get community members
                MATCH (e:Entity {community_id: $community_id})
                WITH collect(e) AS members
                
                // Count internal relationships
                UNWIND members AS e1
                MATCH (e1)-[r:RELATED_TO]-(e2:Entity {community_id: $community_id})
                WHERE id(e1) < id(e2)  // Avoid counting twice
                
                // Return summary
                WITH members, count(DISTINCT r) AS rel_count
                RETURN 
                    size(members) AS entity_count,
                    [m IN members[0..5] | {name: m.name, type: m.type}] AS top_entities,
                    rel_count
                """,
                community_id=community_id,
            )
            
            record = await result.single()
            if not record:
                return {"error": f"Community {community_id} not found"}
            
            return {
                "community_id": community_id,
                "entity_count": record["entity_count"],
                "top_entities": record["top_entities"],
                "relationship_count": record["rel_count"],
            }
    
    async def get_entity_neighborhood(
        self,
        entity_name: str,
        hops: int = 2,
        limit: int = 50,
    ) -> dict:
        """
        Get the N-hop neighborhood of an entity for visualization.
        
        Args:
            entity_name: Name of the central entity
            hops: Number of relationship hops (1-3)
            limit: Maximum nodes to return
            
        Returns:
            Dict with nodes and edges for graph visualization
        """
        if not self._neo4j_driver:
            raise RuntimeError("Neo4j driver not initialized. Use async context manager.")
        
        hops = min(max(hops, 1), 3)  # Clamp to 1-3
        
        async with self._neo4j_driver.session() as session:
            result = await session.run(
                """
                // Find entity by normalized name
                MATCH (center:Entity)
                WHERE toLower(center.name) = toLower($entity_name)
                
                // Variable length path for N hops
                CALL {
                    WITH center
                    MATCH path = (center)-[*1..$hops]-(neighbor:Entity)
                    RETURN neighbor, relationships(path) AS rels
                    LIMIT $limit
                }
                
                // Collect nodes and edges
                WITH center, collect(DISTINCT neighbor) AS neighbors,
                     collect(DISTINCT rels) AS all_rels
                
                RETURN 
                    {name: center.name, type: center.type, id: center.normalized_name} AS center_node,
                    [n IN neighbors | {name: n.name, type: n.type, id: n.normalized_name}] AS neighbor_nodes,
                    size(neighbors) AS neighbor_count
                """,
                entity_name=entity_name,
                hops=hops,
                limit=limit,
            )
            
            record = await result.single()
            if not record:
                return {"error": f"Entity '{entity_name}' not found"}
            
            return {
                "center": record["center_node"],
                "neighbors": record["neighbor_nodes"],
                "neighbor_count": record["neighbor_count"],
                "hops": hops,
            }
    async def get_graph_data(self, limit: int = 500) -> dict:
        """
        Get nodes and edges for 3D graph visualization.
        
        Args:
            limit: Maximum number of relationships to return
            
        Returns:
            Dict with 'nodes' and 'links' list
        """
        if not self._neo4j_driver:
            raise RuntimeError("Neo4j driver not initialized. Use async context manager.")
        
        async with self._neo4j_driver.session() as session:
            # We fetch relationships and their connected nodes
            # This ensures we don't have dangling links
            result = await session.run(
                """
                MATCH (n)-[r:RELATED_TO]-(m)
                RETURN n, r, m
                LIMIT $limit
                """,
                limit=limit,
            )
            
            nodes = {}
            links = []
            
            async for record in result:
                n, r, m = record["n"], record["r"], record["m"]
                
                # Deduplicate nodes by ID
                if n["normalized_name"] not in nodes:
                    nodes[n["normalized_name"]] = {
                        "id": n["normalized_name"],
                        "name": n.get("name", n["normalized_name"]),
                        "type": n.get("type", "CONCEPT"),
                        "description": n.get("description", ""),
                        "val": 1 # for size
                    }
                
                if m["normalized_name"] not in nodes:
                    nodes[m["normalized_name"]] = {
                        "id": m["normalized_name"],
                        "name": m.get("name", m["normalized_name"]),
                        "type": m.get("type", "CONCEPT"),
                        "description": m.get("description", ""),
                        "val": 1
                    }
                    
                links.append({
                    "source": n["normalized_name"],
                    "target": m["normalized_name"],
                    "type": r.get("type", "RELATED_TO"),
                    "weight": r.get("weight", 1.0)
                })
                
            return {
                "nodes": list(nodes.values()),
                "links": links
            }

    async def get_all_documents(self) -> list[dict]:
        """
        Get a list of all ingested documents.

        Returns:
            List of dicts with document metadata.
        """
        if not self._neo4j_driver:
             raise RuntimeError("Neo4j driver not initialized. Use async context manager.")

        async with self._neo4j_driver.session() as session:
            result = await session.run(
                """
                MATCH (d:Document)
                OPTIONAL MATCH (d)-[:HAS_CHUNK]->(c:Chunk)
                WITH d, count(c) as chunk_count
                RETURN d, chunk_count
                ORDER BY d.upload_date DESC
                """
            )
            
            documents = []
            async for record in result:
                d = record["d"]
                documents.append({
                    "id": d["id"],
                    "title": d.get("filename", "Untitled"),
                    "filename": d.get("filename", ""),
                    "uploaded_at": d.get("upload_date", ""),
                    "file_size": d.get("file_size_bytes", 0),
                    "chunk_count": record["chunk_count"],
                    "status": "ready" # Logic could be more complex
                })
            
            return documents
