def allocate(order_size, venues, lambda_over, lambda_under, theta_queue, step=100):
    len_venues = len(venues)
    visited = {}

    def recursive(venue_index, remaining):
        if venue_index == len_venues:
            if remaining == 0:
                return 0.0, []
            return float('inf'), []

        if (venue_index, remaining) in visited:
            return visited[(venue_index, remaining)]

        best_cost = float('inf')
        best_alloc = []

        venue = venues[venue_index]
        max_fill = min(remaining, venue.ask_size)

        for q in range(0, max_fill + 1, step):
            next_cost, next_alloc = recursive(venue_index + 1, remaining - q)
            if next_cost != float('inf'):
                alloc = [q] + next_alloc
                padded_alloc = alloc + [0] * (len_venues - len(alloc))
                cost = compute_cost(padded_alloc, venues, order_size, lambda_over, lambda_under, theta_queue)

                if cost < best_cost:
                    best_cost = cost
                    best_alloc = alloc

        visited[(venue_index, remaining)] = (best_cost, best_alloc)
        return best_cost, best_alloc

    cost, alloc = recursive(0, order_size)
    final_alloc = alloc + [0] * (len(venues) - len(alloc))
    return final_alloc, cost


def compute_cost(split, venues, order_size, lambda_over, lambda_under, theta_queue):
    executed = 0
    cash_spent = 0

    for i in range(len(venues)):
        filled = min(split[i], venues[i].ask_size)
        executed += filled
        cash_spent += filled * (venues[i].ask + venues[i].fee)
        cash_spent -= max(split[i] - filled, 0) * venues[i].rebate

    underfill = max(order_size - executed, 0)
    overfill = max(executed - order_size, 0)
    penalty = theta_queue * (underfill + overfill)
    cost_penalty = lambda_under * underfill + lambda_over * overfill

    return cash_spent + penalty + cost_penalty
