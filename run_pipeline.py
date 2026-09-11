"""
Локальный оркестратор пайплайна розничных рисков.
Запускает все шаги последовательно в текущем процессе.

Использование:
    python run_pipeline.py
"""
import importlib.util
import sys
import time
import traceback
from datetime import datetime


class PipelineStep:
    """Один шаг пайплайна."""
    def __init__(self, name: str, script_path: str):
        self.name = name
        self.script_path = script_path
        self.status = "PENDING"
        self.duration = 0
        self.error = None

    def run(self):
        """Запуск шага в текущем процессе."""
        print(f"\n{'='*60}")
        print(f"▶ Запуск: {self.name}")
        print(f"{'='*60}")

        start_time = time.time()

        try:
            # Загружаем модуль из файла и запускаем его
            spec = importlib.util.spec_from_file_location("module", self.script_path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            self.status = "SUCCESS"

        except Exception as e:
            self.status = "FAILED"
            self.error = str(e)
            print(f"\n✗ Ошибка: {e}")
            traceback.print_exc()

        finally:
            self.duration = time.time() - start_time
            print(f"\n⏱ Время выполнения: {self.duration:.1f} сек")


def main():
    """Запуск пайплайна."""
    print("\n" + "="*60)
    print("ПАЙПЛАИН РОЗНИЧНЫХ КРЕДИТНЫХ РИСКОВ (МСФО 9)")
    print("="*60)
    print(f"Время запуска: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Интерпретатор: {sys.executable}")

    # Определяем шаги пайплайна
    steps = [
        PipelineStep("Шаг 1: Генерация данных", "src/generators/data_generator.py"),
        PipelineStep("Шаг 2: Построение измерений", "src/transform/build_dimensions.py"),
        PipelineStep("Шаг 3: Построение факта платежей", "src/transform/build_fact_payments.py"),
        PipelineStep("Шаг 4: Расчет витрины статусов", "src/transform/build_fact_status.py"),
    ]

    # Запускаем шаги последовательно
    for step in steps:
        step.run()
        if step.status == "FAILED":
            print(f"\n✗ Пайплайн остановлен на шаге: {step.name}")
            return False

    # Итоговый отчет
    print("\n" + "="*60)
    print("ИТОГОВЫЙ ОТЧЕТ ПАЙПЛАЙНА")
    print("="*60)

    total_time = sum(s.duration for s in steps)
    success_count = sum(1 for s in steps if s.status == "SUCCESS")

    for step in steps:
        status_icon = "✓" if step.status == "SUCCESS" else "✗"
        print(f"  {status_icon} {step.name}: {step.status} ({step.duration:.1f}s)")

    print(f"\nВсего времени: {total_time:.1f} сек")
    print(f"Успешных шагов: {success_count}/{len(steps)}")

    if success_count == len(steps):
        print("\n🎉 ПАЙПЛАИН ЗАВЕРШЕН УСПЕШНО!")
        print("Результаты доступны в папке: data/processed/")
        return True
    else:
        print("\n⚠ ПАЙПЛАИН ЗАВЕРШЕН С ОШИБКАМИ")
        return False


if __name__ == "__main__":
    main()