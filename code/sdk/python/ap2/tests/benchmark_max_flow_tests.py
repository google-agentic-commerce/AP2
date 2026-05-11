import timeit
import unittest

from ap2.sdk.generated.open_checkout_mandate import Item as MandateItem
from ap2.sdk.generated.open_checkout_mandate import LineItemRequirements
from ap2.sdk.generated.types.item import Item
from ap2.sdk.generated.types.line_item import LineItem
from ap2.sdk.generated.types.total import Total
from ap2.sdk.max_flow_helper import evaluate_line_items_max_flow


def _li(sku: str, qty: int = 1) -> LineItem:
    return LineItem(
        id=f'li_{sku}',
        item=Item(id=sku, title=sku, price=0),
        quantity=qty,
        totals=[Total(type='total', amount=0)],
    )


def _req(req_id: str, skus: list[str], qty: int) -> LineItemRequirements:
    return LineItemRequirements(
        id=req_id,
        acceptable_items=[MandateItem(id=s, title=s) for s in skus],
        quantity=qty,
    )


class TestDinicVsEdmondsKarp(unittest.TestCase):
    def test_correctness(self):
        """Ensure both algorithms yield the exact same results before benchmarking."""
        skus = [f'item_{i}' for i in range(20)]
        cart = [_li(s, 10) for s in skus]
        reqs = [
            _req(f'req_{r}', [skus[(r + k) % 20] for k in range(5)], 50)
            for r in range(10)
        ]

        self.assertEqual(
            evaluate_line_items_max_flow(cart, reqs, mode='dinic'),
            evaluate_line_items_max_flow(cart, reqs, mode='edmonds_karp'),
        )

    def run_benchmark(
        self, name: str, cart: list, reqs: list, iterations: int = 1000
    ):
        """Helper to run a clean benchmark using timeit."""

        def run_dinic():
            evaluate_line_items_max_flow(cart, reqs, mode='dinic')

        def run_ek():
            evaluate_line_items_max_flow(cart, reqs, mode='edmonds_karp')

        # timeit automatically disables GC and runs the loop efficiently in C
        dinic_time = timeit.timeit(run_dinic, number=iterations)
        ek_time = timeit.timeit(run_ek, number=iterations)

        print(f'\n--- {name} ({iterations} runs) ---')
        print(f'Dinic Avg:        {dinic_time / iterations:.6f} s')
        print(f'Edmonds-Karp Avg: {ek_time / iterations:.6f} s')

        if dinic_time < ek_time:
            print(f'Winner: Dinic by {ek_time / dinic_time:.2f}x')
        else:
            print(f'Winner: Edmonds-Karp by {dinic_time / ek_time:.2f}x')

    def test_benchmarks(self):
        """Run the actual performance comparisons."""

        # 1. Simple 1-to-1 Case
        cart_simple = [_li(f'item_{i}', 1) for i in range(10)]
        reqs_simple = [_req(f'req_{i}', [f'item_{i}'], 1) for i in range(10)]
        self.run_benchmark(
            'Simple 1-to-1 Case', cart_simple, reqs_simple, iterations=2000
        )

        # 2. Medium Dense Case
        skus_med = [f'item_{i}' for i in range(50)]
        cart_med = [_li(s, 100) for s in skus_med]
        reqs_med = [
            _req(f'req_{r}', [skus_med[(r + k) % 50] for k in range(30)], 250)
            for r in range(20)
        ]
        self.run_benchmark(
            'Medium Dense Case', cart_med, reqs_med, iterations=1000
        )

        # 3. Massive Scale Case
        skus_massive = [f'item_{i}' for i in range(300)]
        cart_massive = [_li(s, 50) for s in skus_massive]
        reqs_massive = [
            _req(
                f'req_{r}',
                [skus_massive[(r + k) % 300] for k in range(50)],
                500,
            )
            for r in range(50)
        ]
        self.run_benchmark(
            'Massive Scale Case', cart_massive, reqs_massive, iterations=100
        )

        # 4. Deep Cascading Chain Case
        # A chain where item 0 matches req 0, item 1 matches req 0 and 1,
        # item 2 matches 1 and 2, etc.
        # This forces the algorithms to do long augmenting paths and
        # backtracking.
        skus_chain = [f'item_{i}' for i in range(100)]
        cart_chain = [_li(s, 10) for s in skus_chain]
        reqs_chain = []
        for i in range(100):
            if i == 0:
                reqs_chain.append(_req('req_0', [skus_chain[0]], 10))
            else:
                reqs_chain.append(
                    _req(f'req_{i}', [skus_chain[i - 1], skus_chain[i]], 10)
                )
        self.run_benchmark(
            'Deep Cascading Chain', cart_chain, reqs_chain, iterations=200
        )

        # 5. Complete Bipartite Graph (K_N,N)
        # Every item matches every requirement. Dense matrix of identical
        # weights.
        skus_complete = [f'item_{i}' for i in range(50)]
        cart_complete = [_li(s, 20) for s in skus_complete]
        reqs_complete = [_req(f'req_{i}', skus_complete, 20) for i in range(50)]
        self.run_benchmark(
            'Complete Bipartite Graph (All Match All)',
            cart_complete,
            reqs_complete,
            iterations=200,
        )


if __name__ == '__main__':
    unittest.main(verbosity=1)
