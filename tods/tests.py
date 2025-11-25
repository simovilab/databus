"""
Unit tests for TODS models and API endpoints.
"""
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APITestCase
from rest_framework import status
from datetime import time, date
from gtfs.models import Feed, Trip, Stop, Route, Agency
from .models import (
    Operator,
    Run,
    RunPiece,
    RunEvent,
    Deadhead,
    DeadheadStopTime,
    RosterAssignment,
)


class TODSModelsTestCase(TestCase):
    """Test TODS model creation and relationships."""
    
    def setUp(self):
        """Set up test data."""
        self.feed = Feed.objects.create(
            feed_id='test_feed',
            is_current=True
        )
        
        self.operator = Operator.objects.create(
            feed=self.feed,
            operator_id='OP001',
            operator_name='Juan Pérez',
            operator_type=0,
            operator_license='LIC12345',
            operator_phone='+50688888888'
        )
    
    def test_operator_creation(self):
        """Test that an operator can be created."""
        self.assertEqual(self.operator.operator_name, 'Juan Pérez')
        self.assertEqual(self.operator.operator_type, 0)
        self.assertEqual(str(self.operator), 'Juan Pérez (OP001)')
    
    def test_run_creation(self):
        """Test that a run can be created and linked to an operator."""
        run = Run.objects.create(
            feed=self.feed,
            run_id='RUN001',
            run_name='Morning Route 1',
            operator=self.operator
        )
        
        self.assertEqual(run.run_id, 'RUN001')
        self.assertEqual(run.operator, self.operator)
        self.assertEqual(str(run), 'Run RUN001')
    
    def test_run_piece_creation(self):
        """Test that run pieces can be created in sequence."""
        run = Run.objects.create(
            feed=self.feed,
            run_id='RUN001',
            operator=self.operator
        )
        
        piece1 = RunPiece.objects.create(
            feed=self.feed,
            run_piece_id='PIECE001',
            run=run,
            piece_type=3,  # Sign on
            start_time=time(6, 0),
            end_time=time(6, 15),
            piece_sequence=1
        )
        
        piece2 = RunPiece.objects.create(
            feed=self.feed,
            run_piece_id='PIECE002',
            run=run,
            piece_type=0,  # Revenue service
            start_time=time(6, 15),
            end_time=time(14, 0),
            piece_sequence=2
        )
        
        self.assertEqual(run.pieces.count(), 2)
        self.assertEqual(piece1.piece_sequence, 1)
        self.assertEqual(piece2.piece_sequence, 2)
    
    def test_deadhead_creation(self):
        """Test that deadheads can be created."""
        stop1 = Stop.objects.create(
            feed=self.feed,
            stop_id='STOP001',
            stop_name='Garage',
            stop_lat=9.9333,
            stop_lon=-84.0833
        )
        
        stop2 = Stop.objects.create(
            feed=self.feed,
            stop_id='STOP002',
            stop_name='Terminal',
            stop_lat=9.9400,
            stop_lon=-84.0900
        )
        
        deadhead = Deadhead.objects.create(
            feed=self.feed,
            deadhead_id='DH001',
            deadhead_type=0,  # Pullout
            from_stop=stop1,
            to_stop=stop2,
            start_time=time(5, 30),
            end_time=time(5, 50)
        )
        
        self.assertEqual(deadhead.deadhead_type, 0)
        self.assertEqual(deadhead.from_stop, stop1)
        self.assertEqual(deadhead.to_stop, stop2)
    
    def test_roster_assignment(self):
        """Test that roster assignments can be created."""
        run = Run.objects.create(
            feed=self.feed,
            run_id='RUN001'
        )
        
        assignment = RosterAssignment.objects.create(
            feed=self.feed,
            roster_id='ROSTER001',
            operator=self.operator,
            run=run,
            assignment_date=date.today()
        )
        
        self.assertEqual(assignment.operator, self.operator)
        self.assertEqual(assignment.run, run)
        self.assertIn('Juan Pérez', str(assignment))


class TODSAPITestCase(APITestCase):
    """Test TODS API endpoints."""
    
    def setUp(self):
        """Set up test data."""
        self.feed = Feed.objects.create(
            feed_id='test_feed',
            is_current=True
        )
        
        self.operator = Operator.objects.create(
            feed=self.feed,
            operator_id='OP001',
            operator_name='María González',
            operator_type=0
        )
        
        self.run = Run.objects.create(
            feed=self.feed,
            run_id='RUN001',
            run_name='Morning Shift',
            operator=self.operator
        )
    
    def test_operators_list(self):
        """Test GET /api/tods/operators/"""
        response = self.client.get('/api/tods/operators/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
        self.assertEqual(response.data['results'][0]['operator_name'], 'María González')
    
    def test_operators_filter_by_type(self):
        """Test filtering operators by type."""
        response = self.client.get('/api/tods/operators/?operator_type=0')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
    
    def test_runs_list(self):
        """Test GET /api/tods/runs/"""
        response = self.client.get('/api/tods/runs/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
        self.assertEqual(response.data['results'][0]['run_id'], 'RUN001')
    
    def test_runs_detail(self):
        """Test GET /api/tods/runs/{id}/"""
        response = self.client.get(f'/api/tods/runs/{self.run.id}/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['run_name'], 'Morning Shift')
        self.assertEqual(response.data['operator_name'], 'María González')
    
    def test_deadheads_list(self):
        """Test GET /api/tods/deadheads/"""
        stop1 = Stop.objects.create(
            feed=self.feed,
            stop_id='STOP001',
            stop_name='Depot',
            stop_lat=9.9333,
            stop_lon=-84.0833
        )
        
        Deadhead.objects.create(
            feed=self.feed,
            deadhead_id='DH001',
            deadhead_type=0,
            from_stop=stop1,
            to_stop=stop1,
            start_time=time(5, 0),
            end_time=time(5, 30)
        )
        
        response = self.client.get('/api/tods/deadheads/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
    
    def test_roster_assignments_list(self):
        """Test GET /api/tods/roster-assignments/"""
        RosterAssignment.objects.create(
            feed=self.feed,
            roster_id='ROSTER001',
            operator=self.operator,
            run=self.run,
            assignment_date=date.today()
        )
        
        response = self.client.get('/api/tods/roster-assignments/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
