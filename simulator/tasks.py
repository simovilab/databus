"""
Celery tasks for periodic simulation updates.
"""

from celery import shared_task
from celery.utils.log import get_task_logger

from .simulator import SimulationManager

logger = get_task_logger(__name__)


@shared_task(name='simulator.update_positions')
def update_simulated_positions():
    """
    Periodic task to update positions for all active simulated vehicles.
    Runs every 10 seconds by default.
    """
    try:
        logger.info("Updating simulated vehicle positions...")
        results = SimulationManager.update_all_positions()
        logger.info(f"Updated {len(results)} vehicle positions")
        return {
            'success': True,
            'updated_count': len(results),
            'results': results
        }
    except Exception as e:
        logger.error(f"Error updating simulated positions: {e}")
        return {
            'success': False,
            'error': str(e)
        }


@shared_task(name='simulator.cleanup_logs')
def cleanup_simulation_logs():
    """
    Periodic task to clean up old simulation logs.
    Runs daily by default.
    """
    try:
        logger.info("Cleaning up old simulation logs...")
        deleted_count = SimulationManager.cleanup_old_logs(days=7)
        logger.info(f"Cleaned up {deleted_count} old logs")
        return {
            'success': True,
            'deleted_count': deleted_count
        }
    except Exception as e:
        logger.error(f"Error cleaning up logs: {e}")
        return {
            'success': False,
            'error': str(e)
        }
