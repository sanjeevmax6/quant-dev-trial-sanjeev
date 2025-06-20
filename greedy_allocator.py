from allocator import compute_cost

# Since in a dry run, I experimented, each snapshots has venues i range (5, 616), the computation could go more than a system can handle. Hence, I have implemented a greedy algorithm below
def greedy_allocate(order_size, venues, λ_over, λ_under, θ_queue):
    # Compute effective cost per venue
    venue_indices = list(range(len(venues)))
    venue_costs = [
        (i, venues[i].ask + venues[i].fee - venues[i].rebate + θ_queue / (venues[i].ask_size + 1e-8))
        for i in venue_indices
    ]

    # Sort venues by effective cost (lowest to highest)
    venue_costs.sort(key=lambda x: x[1])

    # Initialize allocation array and remaining order
    alloc = [0] * len(venues)
    remaining = order_size

    for i, _ in venue_costs:
        available = venues[i].ask_size
        qty = min(available, remaining)
        alloc[i] = qty
        remaining -= qty
        if remaining == 0:
            break

    # If we couldn't allocate the full order_size, that's okay — underfill handled in compute_cost
    best_cost = compute_cost(alloc, venues, order_size, λ_over, λ_under, θ_queue)
    return alloc, best_cost