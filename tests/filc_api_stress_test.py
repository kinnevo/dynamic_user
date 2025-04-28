import asyncio
import time
import uuid
import random
import sys
import statistics
import threading
import os
import multiprocessing
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple

# Add parent directory to path to import the FilcAgentClient
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from utils.filc_agent_client import FilcAgentClient

# Configure test parameters
TEST_CONCURRENCY_LEVELS = [5, 20, 50]  # Number of concurrent users
MESSAGES_PER_USER = 3  # Number of messages each user will send
DELAY_BETWEEN_WAVES = 5.0  # Seconds to wait between message waves
TIMEOUT_SECONDS = 60  # Maximum time to wait for each API call
SHOW_INDIVIDUAL_REQUESTS = True  # Set to False for cleaner output with large concurrency
VISUALIZE_CONCURRENCY = True  # Set to True to see concurrent execution pattern
MAX_PARALLEL_TASKS = 100  # Ensure we don't overwhelm the system

# Sample conversation topics to make the test more realistic
CONVERSATION_STARTERS = [
    "Quiero abrir un negocio de comida mexicana en San Francisco",
    "Necesito ayuda para crear un plan de negocio para una cafetería",
    "Me gustaría saber cómo iniciar un restaurante de comida italiana",
    "Estoy pensando en abrir una panadería, ¿qué debo considerar?",
    "¿Qué trámites se necesitan para abrir un food truck?",
    "Quiero invertir en un negocio de catering, ¿es rentable?",
    "¿Cómo puedo obtener financiamiento para mi negocio de comida?",
    "Me interesa crear una app de delivery de comida",
    "¿Qué permisos necesito para vender comida preparada en casa?",
    "¿Cuál es la mejor ubicación para un restaurante en Chicago?",
]

# Follow-up questions to simulate real conversations
FOLLOW_UP_QUESTIONS = [
    "¿Puedes explicar eso con más detalle?",
    "¿Cuáles son las aplicaciones prácticas de esto?",
    "¿Cómo se compara esto con otros enfoques?",
    "¿Cuáles son las limitaciones de este enfoque?",
    "¿Puedes proporcionar un ejemplo?",
    "¿Cuáles son los desarrollos más recientes en esta área?",
    "¿Cómo implementaría esto en mi negocio?",
    "¿Qué recursos recomendarías para aprender más?",
    "¿Hay alternativas que debería considerar?",
    "¿Cómo funcionaría esto a escala?",
]


class StressTestResults:
    """Class to store and analyze stress test results"""
    
    def __init__(self, concurrency_level: int, test_type: str):
        self.concurrency_level = concurrency_level
        self.test_type = test_type  # "async" or "sync"
        self.response_times = []
        self.errors = []
        self.start_time = None
        self.end_time = None
        self.successful_requests = 0
        self.failed_requests = 0
        self.wave_stats = []  # Store stats for each wave of requests
    
    def start_test(self):
        self.start_time = time.time()
    
    def end_test(self):
        self.end_time = time.time()
    
    def start_wave(self, wave_num: int):
        """Record the start of a new wave of concurrent requests"""
        self.wave_stats.append({
            "wave": wave_num,
            "start_time": time.time(),
            "end_time": None,
            "response_times": [],
            "success_count": 0,
            "error_count": 0
        })
    
    def end_wave(self, wave_num: int):
        """Record the end of a wave of concurrent requests"""
        for stat in self.wave_stats:
            if stat["wave"] == wave_num and stat["end_time"] is None:
                stat["end_time"] = time.time()
                break
    
    def add_result(self, response_time: float, success: bool, error_msg: Optional[str] = None, wave_num: Optional[int] = None):
        if success:
            self.response_times.append(response_time)
            self.successful_requests += 1
        else:
            self.errors.append(error_msg)
            self.failed_requests += 1
            
        # Add to wave stats if provided
        if wave_num is not None:
            for stat in self.wave_stats:
                if stat["wave"] == wave_num:
                    if success:
                        stat["response_times"].append(response_time)
                        stat["success_count"] += 1
                    else:
                        stat["error_count"] += 1
                    break
    
    def get_summary(self) -> Dict[str, Any]:
        """Generate a summary of the test results"""
        total_duration = self.end_time - self.start_time if self.end_time else 0
        total_requests = self.successful_requests + self.failed_requests
        
        # Calculate statistics only if we have successful responses
        if self.response_times:
            avg_response_time = statistics.mean(self.response_times)
            median_response_time = statistics.median(self.response_times)
            min_response_time = min(self.response_times)
            max_response_time = max(self.response_times)
            
            # Calculate 95th percentile
            sorted_times = sorted(self.response_times)
            p95_index = int(len(sorted_times) * 0.95)
            p95_time = sorted_times[p95_index]
            
            # Calculate standard deviation if we have enough data points
            stdev_response_time = statistics.stdev(self.response_times) if len(self.response_times) > 1 else 0
        else:
            avg_response_time = median_response_time = min_response_time = max_response_time = p95_time = stdev_response_time = 0
        
        success_rate = (self.successful_requests / total_requests * 100) if total_requests > 0 else 0
        requests_per_second = total_requests / total_duration if total_duration > 0 else 0
        
        # Calculate wave statistics
        wave_summaries = []
        for wave in self.wave_stats:
            if wave["response_times"]:
                wave_avg = statistics.mean(wave["response_times"])
                wave_max = max(wave["response_times"])
                wave_duration = wave["end_time"] - wave["start_time"] if wave["end_time"] else 0
            else:
                wave_avg = wave_max = wave_duration = 0
                
            wave_summaries.append({
                "wave": wave["wave"],
                "requests": wave["success_count"] + wave["error_count"],
                "success_rate": (wave["success_count"] / (wave["success_count"] + wave["error_count"])) * 100 if (wave["success_count"] + wave["error_count"]) > 0 else 0,
                "avg_response_time": wave_avg,
                "max_response_time": wave_max,
                "duration": wave_duration
            })
        
        return {
            "test_type": self.test_type,
            "concurrency_level": self.concurrency_level,
            "total_requests": total_requests,
            "successful_requests": self.successful_requests,
            "failed_requests": self.failed_requests,
            "success_rate": success_rate,
            "total_duration_seconds": total_duration,
            "requests_per_second": requests_per_second,
            "avg_response_time": avg_response_time,
            "median_response_time": median_response_time,
            "min_response_time": min_response_time,
            "max_response_time": max_response_time,
            "p95_response_time": p95_time,
            "stdev_response_time": stdev_response_time,
            "error_count": len(self.errors),
            "wave_stats": wave_summaries
        }


async def send_message_async(user_id: int, message: str, session_id: str, history: List, 
                             results: StressTestResults, client: FilcAgentClient, wave_num: int) -> Tuple[List, bool]:
    """Send a single message asynchronously and return the updated history"""
    # Visual indicator of concurrent execution start
    start_timestamp = time.time()
    start_time_str = datetime.fromtimestamp(start_timestamp).strftime('%H:%M:%S.%f')[:-3]
    
    if SHOW_INDIVIDUAL_REQUESTS:
        print(f"[{start_time_str}] User {user_id} STARTING request in wave {wave_num}: {message[:30]}...")
    
    try:
        response = await client.process_message(
            message=message,
            session_id=session_id,
            history=history
        )
        
        # Visual indicator of concurrent execution completion
        end_timestamp = time.time()
        end_time_str = datetime.fromtimestamp(end_timestamp).strftime('%H:%M:%S.%f')[:-3]
        response_time = end_timestamp - start_timestamp
        
        success = "error" not in response
        results.add_result(response_time, success, 
                          str(response.get("error")) if not success else None, 
                          wave_num)
        
        # Make a copy of history to avoid reference issues
        updated_history = history.copy() if history else []
        
        if success:
            # Update history
            updated_history.append({"role": "user", "content": message})
            updated_history.append({"role": "assistant", "content": response.get("content", "")})
            if SHOW_INDIVIDUAL_REQUESTS:
                print(f"[{end_time_str}] User {user_id} COMPLETED in {response_time:.2f}s")
        else:
            if SHOW_INDIVIDUAL_REQUESTS:
                print(f"[{end_time_str}] User {user_id} ERROR in {response_time:.2f}s: {response.get('error', 'Unknown error')}")
        
        return updated_history, success
        
    except Exception as e:
        end_time_str = datetime.fromtimestamp(time.time()).strftime('%H:%M:%S.%f')[:-3]
        results.add_result(0, False, str(e), wave_num)
        if SHOW_INDIVIDUAL_REQUESTS:
            print(f"[{end_time_str}] User {user_id} EXCEPTION: {str(e)}")
        return history, False


async def run_async_wave_test(concurrency: int) -> StressTestResults:
    """Run an async concurrent test with waves of simultaneous requests"""
    client = FilcAgentClient()
    results = StressTestResults(concurrency, "async")
    
    print(f"\n{'='*80}\nStarting ASYNC WAVE test with {concurrency} concurrent users\n{'='*80}")
    results.start_test()
    
    # Create session IDs and starter messages for all users
    sessions = []
    for i in range(concurrency):
        sessions.append({
            "user_id": i,
            "session_id": str(uuid.uuid4()),
            "history": [],
            "success": True
        })
    
    # Send messages in waves
    for wave in range(MESSAGES_PER_USER):
        wave_num = wave + 1
        print(f"\n▶▶▶ WAVE {wave_num}: SENDING {concurrency} SIMULTANEOUS REQUESTS ▶▶▶")
        results.start_wave(wave_num)
        
        start_time = time.time()
        active_sessions = [s for s in sessions if s["success"]]
        
        # Create tasks for all users in this wave
        tasks = []
        
        if VISUALIZE_CONCURRENCY:
            # Print visual separator to show wave start
            print("\n" + "-" * 40)
            print(f"Wave {wave_num} execution pattern (each '.' is a request):")
            print("-" * 40)
        
        for session in active_sessions:
            message = random.choice(CONVERSATION_STARTERS if wave == 0 else FOLLOW_UP_QUESTIONS)
            
            # Create a task for each user
            task = send_message_async(
                session["user_id"],
                message,
                session["session_id"],
                session["history"],
                results,
                client,
                wave_num
            )
            tasks.append((session, task))
            
            if VISUALIZE_CONCURRENCY:
                # Print a dot without newline to visualize request start
                print(".", end="", flush=True)
                # Add a small delay between task creation for clarity
                await asyncio.sleep(0.01)
        
        if VISUALIZE_CONCURRENCY:
            print("\n" + "-" * 40)
        
        # Execute all requests concurrently with gather
        if tasks:
            print(f"\nStarting {len(tasks)} concurrent API calls at {datetime.now().strftime('%H:%M:%S.%f')[:-3]}...")
            
            # Run tasks in batches to prevent overwhelming the event loop
            batch_size = min(MAX_PARALLEL_TASKS, len(tasks))
            for i in range(0, len(tasks), batch_size):
                batch = tasks[i:i+batch_size]
                
                batch_sessions = [session for session, _ in batch]
                batch_tasks = [task for _, task in batch]
                
                try:
                    # This is where true concurrency happens
                    batch_responses = await asyncio.gather(*batch_tasks, return_exceptions=True)
                    
                    # Process results
                    for j, response in enumerate(batch_responses):
                        if isinstance(response, Exception):
                            batch_sessions[j]["success"] = False
                            print(f"Error in task: {str(response)}")
                        else:
                            history, success = response
                            batch_sessions[j]["history"] = history
                            batch_sessions[j]["success"] = success
                except Exception as e:
                    print(f"Error during gather operation: {str(e)}")
        
        # End of wave timing
        duration = time.time() - start_time
        active_user_count = sum(1 for s in sessions if s["success"])
        results.end_wave(wave_num)
        
        print(f"◀◀◀ WAVE {wave_num} COMPLETED: {active_user_count}/{concurrency} active users, took {duration:.2f}s ◀◀◀")
        
        # If all sessions failed, stop testing
        if active_user_count == 0:
            print("All sessions have failed. Stopping test.")
            break
            
        # Wait between waves
        if wave < MESSAGES_PER_USER - 1:
            print(f"Waiting {DELAY_BETWEEN_WAVES} seconds before next wave...")
            await asyncio.sleep(DELAY_BETWEEN_WAVES)
    
    results.end_test()
    return results


def print_results(results: StressTestResults) -> None:
    """Print formatted results of a test"""
    summary = results.get_summary()
    
    print(f"\n{'='*80}")
    print(f"TEST RESULTS: {summary['concurrency_level']} concurrent users - {summary['test_type'].upper()}")
    print(f"{'='*80}")
    print(f"Total requests:        {summary['total_requests']}")
    print(f"Successful requests:   {summary['successful_requests']} ({summary['success_rate']:.2f}%)")
    print(f"Failed requests:       {summary['failed_requests']}")
    print(f"Total duration:        {summary['total_duration_seconds']:.2f} seconds")
    print(f"Requests per second:   {summary['requests_per_second']:.2f}")
    print(f"\nResponse Time Statistics (seconds):")
    print(f"  Average:             {summary['avg_response_time']:.2f}")
    print(f"  Median:              {summary['median_response_time']:.2f}")
    print(f"  Min:                 {summary['min_response_time']:.2f}")
    print(f"  Max:                 {summary['max_response_time']:.2f}")
    print(f"  95th percentile:     {summary['p95_response_time']:.2f}")
    print(f"  Standard deviation:  {summary['stdev_response_time']:.2f}")
    
    print(f"\nWave Statistics:")
    for wave in summary["wave_stats"]:
        print(f"  Wave {wave['wave']}: {wave['requests']} requests, "
              f"{wave['success_rate']:.1f}% success rate, "
              f"avg: {wave['avg_response_time']:.2f}s, max: {wave['max_response_time']:.2f}s")
    
    print(f"{'='*80}\n")


def save_results_to_file(all_results: List[StressTestResults]) -> None:
    """Save test results to a file"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"filc_stress_test_{timestamp}.txt"
    
    with open(filename, 'w') as f:
        f.write(f"FILC Agent API Stress Test Results - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        f.write(f"Test Configuration:\n")
        f.write(f"- Concurrency levels: {TEST_CONCURRENCY_LEVELS}\n")
        f.write(f"- Messages per user: {MESSAGES_PER_USER}\n")
        f.write(f"- Delay between waves: {DELAY_BETWEEN_WAVES} seconds\n\n")
        
        for results in all_results:
            summary = results.get_summary()
            f.write(f"Test Type: {summary['test_type'].upper()} - {summary['concurrency_level']} concurrent users\n")
            f.write(f"Total requests: {summary['total_requests']}\n")
            f.write(f"Success rate: {summary['success_rate']:.2f}%\n")
            f.write(f"Requests per second: {summary['requests_per_second']:.2f}\n")
            f.write(f"Average response time: {summary['avg_response_time']:.2f} seconds\n")
            f.write(f"95th percentile response time: {summary['p95_response_time']:.2f} seconds\n")
            
            f.write("\nWave Statistics:\n")
            for wave in summary["wave_stats"]:
                f.write(f"  Wave {wave['wave']}: {wave['requests']} requests, "
                      f"{wave['success_rate']:.1f}% success, "
                      f"avg: {wave['avg_response_time']:.2f}s, "
                      f"max: {wave['max_response_time']:.2f}s, "
                      f"duration: {wave['duration']:.2f}s\n")
            f.write("\n")
            
            if summary["error_count"] > 0:
                f.write(f"Errors: {summary['error_count']}\n\n")
    
    print(f"Results saved to {filename}")


async def main():
    """Main function to run all tests"""
    print(f"Starting FILC Agent API stress test at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Testing with {MESSAGES_PER_USER} messages per user at concurrency levels: {TEST_CONCURRENCY_LEVELS}")
    
    # Check connection before starting tests
    client = FilcAgentClient()
    is_connected, message = await client.check_connection()
    
    if not is_connected:
        print(f"ERROR: Cannot connect to FILC Agent API: {message}")
        print("Please check your connection settings and try again.")
        return
    
    print(f"Successfully connected to FILC Agent API at {client.base_url}")
    
    # Validate configuration
    print("\nValidating test configuration...")
    
    try:
        # Simple connection test to verify endpoint reachability
        print("- Testing API endpoint with single request...")
        test_msg = "Hola, este es un mensaje de prueba"
        start = time.time()
        test_response = await client.process_message(test_msg, str(uuid.uuid4()), [])
        duration = time.time() - start
        
        if "error" in test_response:
            print(f"  ⚠️ WARNING: Test request returned error: {test_response.get('error')}")
            print("  Tests will proceed but may encounter similar errors")
        else:
            print(f"  ✓ Test request successful ({duration:.2f}s)")
    except Exception as e:
        print(f"  ❌ Test request failed: {str(e)}")
        print("  Tests will proceed but may encounter similar errors")
    
    all_results = []
    
    # Run async tests with different concurrency levels
    for concurrency in TEST_CONCURRENCY_LEVELS:
        try:
            results = await run_async_wave_test(concurrency)
            all_results.append(results)
            print_results(results)
        except Exception as e:
            print(f"ERROR: Async test with {concurrency} users failed: {str(e)}")
            print("Skipping to next test...")
    
    # Save all results to file
    save_results_to_file(all_results)
    
    print("\nStress test completed!")


if __name__ == "__main__":
    # Setup asyncio policies for better performance
    try:
        import uvloop
        uvloop.install()
        print("Using uvloop for improved async performance")
    except ImportError:
        print("uvloop not available, using standard asyncio event loop")
    
    # Run the main async function
    asyncio.run(main())