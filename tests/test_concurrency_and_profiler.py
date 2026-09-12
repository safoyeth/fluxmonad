from fluxmonad import Flux


def test_parallel_map_thread():
    data = [1, 2, 3, 4, 5]
    res = (
        Flux(data)
        .parallel_map(lambda x: x * 10, workers=2, backend="thread")
        .collect()
    )
    assert res == [10, 20, 30, 40, 50]


def test_profiler():
    profile_info = (
        Flux(range(50))
        .when(lambda x: x % 2 == 0)
        .map(lambda x: x * 2)
        .profile()
    )

    summary_str = profile_info.summary()

    assert "Pipeline Profile" in summary_str
    assert len(profile_info.result) == 25
    assert len(profile_info.metrics) >= 3
    assert profile_info.metrics[-1].items_processed == 25