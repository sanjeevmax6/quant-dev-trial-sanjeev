def allocate(order_size, venues, lambda_over, lambda_under, theta_queue, step=100):
    len_venues = len(venues)
    visited = {}

    def recursive(venue_index, remaining):
        if venue_index == len_venues:
            if remaining == 0:
                return 0.0, []
            else:
                return float('inf'), []
        
        if (venue_index, remaining) in visited:
            return visited[(venue_index, remaining)]
        
        best_cost = float('inf')
        splits = []
        
        venue = venues[venue_index]
        max_v = min(remaining, venue.ask_size)

        for q in range(0, max_v, step):
            next_cost, next_alloc = recursive(venue_index+1, remaining - q)

            if next_cost != float('inf'):
                new_splits = [q] + next_alloc

                if venue_index == 0:
                    total_cost = compute_cost(new_splits, venues, order_size, lambda_over, lambda_under, theta_queue)
                else:
                    total_cost = next_cost

                if total_cost < best_cost:
                    best_cost = total_cost
                    splits = new_splits
        
        if max_v > 0 and max_v % step != 0:
            q = max_v
            next_cost, next_alloc = recursive(venue_index + 1, remaining - q)

            if next_cost != float('inf'):
                new_splits = [q] + next_alloc

                if venue_index == 0:
                    total_cost = compute_cost(new_splits, venues, order_size, lambda_over, lambda_under, theta_queue)
                else:
                    total_cost = next_cost
                
                if total_cost < best_cost:
                    best_cost = total_cost
                    splits = new_splits

        visited[(venue_index, remaining)] = (best_cost, splits)
        return best_cost, splits
    
    cost, alloc = recursive(0, order_size)


    if alloc:
        final_allocation = alloc + [0] * (len_venues - len(alloc))
        return final_allocation, cost
    else:
        return [0] * len_venues, float('inf')


def compute_cost(split, venues, order_size, lambda_over, lambda_under, theta_queue):
    executed = 0
    cash_spent = 0

    for i, venue in enumerate(venues):
        curr_exec = min(split[i], venue.ask_size)
        executed += curr_exec
        cash_spent += curr_exec * (venue.ask + venue.fee)
        maker_rebate = max(split[i]-curr_exec, 0) * venue.rebate
        cash_spent -= maker_rebate

    underfill = max(order_size-executed, 0)
    overfill = max(executed-order_size, 0)
    risk_pen = theta_queue * (underfill + overfill)
    cost_pen = lambda_under * underfill + lambda_over * overfill

    return cash_spent + risk_pen + cost_pen