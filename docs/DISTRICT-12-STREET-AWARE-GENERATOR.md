# District 12 street-aware runtime generator

The first dense-city pass proved that runtime cloning works, but a player-centered rectangular grid produced visible urban nonsense: towers, storefront pieces and props could be placed without regard to the authored street network.

The current generator therefore treats the existing Cyberpunk Streets road entities as the authoritative urban plan.

## Rules

- Existing road entities define where the city is allowed to grow.
- Straight-road samples create building sites on both sides of the street, not in the carriageway.
- Intersection samples create corner sites while preserving intersection clearance.
- Candidate sites are rejected when they are too close to another road, existing authored architecture, the player spawn, or steep terrain relative to the nearby road.
- Building sites are spatially deduplicated so adjacent road meshes form continuous blocks instead of overlapping piles.
- Every few frontage sites intentionally become alley mouths; deeper infill behind those gaps maintains urban mass while leaving a readable service corridor from the street.
- Street props are tied to road anchors at consistent curb offsets. Loose storefront modules are not spawned as freestanding kiosks.
- Building height increases slightly in deeper/back-row sites so the street edge remains readable and the skyline rises behind it.
- Runtime creation remains incremental to keep GameGuru MAX responsive.

This system is meant to provide coherent background and midground city fabric. Hero storefronts, alleys, signage and cinematic compositions are still authored by hand in GameGuru MAX/CineGuru.
