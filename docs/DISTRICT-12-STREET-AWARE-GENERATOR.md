# District 12 street-aware runtime generator

The first dense-city pass proved that runtime cloning works, but a player-centered rectangular grid produced visible urban nonsense: towers, storefront pieces and props could be placed without regard to the authored street network.

The generator now treats the existing Cyberpunk Streets road entities as the authoritative urban plan **and uses real entity footprints for placement safety**.

## Placement rules

- Existing road entities define where the city is allowed to grow.
- Every road is converted from its actual GameGuru collision bounds, scale and Y rotation into a 2D oriented bounding box (OBB).
- Existing authored Cyberpunk architecture is also registered as occupied OBB space before any generated building is planned.
- Candidate generated buildings use the collision bounds of the actual building kit they will spawn, including scale and rotation.
- A separating-axis OBB test rejects any building whose footprint intersects a road footprint, existing authored architecture, or a previously accepted generated building.
- Safety margins are added around roads and buildings, so merely touching bounding boxes is also rejected.
- Candidate sites may be pushed outward from a street several times when the first frontage position is too tight; they are never allowed to resolve inward into the carriageway.
- Straight-road samples create coherent frontage, back-row and sparse deep-row sites on both sides of the street.
- Intersection samples create corner masses while preserving the full footprint of T and 4-way road pieces.
- Every few frontage sites intentionally become alley mouths; deeper infill behind those gaps maintains urban mass while leaving a readable service corridor.
- The center and all four corners of each accepted building footprint are sampled with `GetTerrainHeight`; steep or hillside-spanning footprints are rejected.
- Street props are tied to road anchors and are separately checked against the road OBBs before spawning.
- Runtime creation remains incremental at three spawned entities per frame so GameGuru MAX stays responsive.

## Diagnostics

The CITY V2 diagnostic reports accepted blocks and also publishes counts for sites rejected because of road intersection, building overlap, or terrain. A lower clone count than the old brute-force pass is expected and desirable: the goal is valid urban geometry, not the maximum possible object count.

This system provides coherent background and midground city fabric. Hero storefronts, signage, unique alleys and cinematic compositions are still authored by hand in GameGuru MAX/CineGuru.
