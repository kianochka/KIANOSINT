class CorrelationEngine:
    def __init__(self, target_username: str) -> None:
        self.target = target_username

    def analyze(self, findings):
        from correlation.signals import detect
        return detect(findings, self.target)

    @staticmethod
    def strength(signals) -> str:
        if not signals:
            return "LOW"
        total = sum(s.weight for s in signals)
        if total >= 1.5:
            return "HIGH"
        if total >= 0.6:
            return "MEDIUM"
        return "LOW"