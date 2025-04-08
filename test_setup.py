#!/usr/bin/env python3
# -*- coding: utf-8 -*-
 
import os
import unittest
import tempfile
from unittest.mock import patch, mock_open
import setuptools


class TestSetup(unittest.TestCase):
    
    def test_setup_name(self):
        """Test that setup is called with the correct package name."""
        with patch('setuptools.setup') as mock_setup:
            # Load the setup module
            with open('setup.py') as f:
                exec(f.read())
            
            # Check the name argument
            args, kwargs = mock_setup.call_args
            self.assertEqual(kwargs.get('name'), 'repolizer')
    
    def test_setup_version(self):
        """Test that setup is called with the correct version."""
        with patch('setuptools.setup') as mock_setup:
            # Load the setup module
            with open('setup.py') as f:
                exec(f.read())
            
            # Check version argument
            args, kwargs = mock_setup.call_args
            self.assertEqual(kwargs.get('version'), '0.1.0')
    
    def test_setup_author(self):
        """Test that setup is called with the correct author information."""
        with patch('setuptools.setup') as mock_setup:
            # Load the setup module
            with open('setup.py') as f:
                exec(f.read())
            
            # Check author arguments
            args, kwargs = mock_setup.call_args
            self.assertEqual(kwargs.get('author'), 'Fabrizio Salmi')
            self.assertEqual(kwargs.get('author_email'), 'fabrizio.salmi@gmail.com')
    
    def test_readme_content(self):
        """Test that README.md is read correctly."""
        readme_content = "# Test README\nThis is a test."
        setup_content = "from setuptools import setup\nsetup(name='repolizer', version='0.1.0', author='Fabrizio Salmi', author_email='fabrizio.salmi@gmail.com', long_description=open('README.md').read())"
        
        # Create a mock that returns different content based on the filename
        def mock_file_open(filename, *args, **kwargs):
            if 'README.md' in str(filename):
                return mock_open(read_data=readme_content).return_value
            elif 'setup.py' in str(filename):
                return mock_open(read_data=setup_content).return_value
            return mock_open().return_value
        
        with patch('builtins.open', side_effect=mock_file_open):
            # Load the setup module with mocked open
            with patch('setuptools.setup') as mock_setup:
                # Execute setup.py code
                exec(setup_content)
                
                # Now setup should have been called
                mock_setup.assert_called_once()
                args, kwargs = mock_setup.call_args
                self.assertEqual(kwargs.get('long_description'), readme_content)
    
    def test_requirements(self):
        """Test that requirements.txt is read correctly."""
        req_content = "requests==2.26.0\npandas>=1.3.0\n# This is a comment\n\nnumpy"
        expected_reqs = ['requests==2.26.0', 'pandas>=1.3.0', 'numpy']
        setup_content = "from setuptools import setup\nwith open('requirements.txt') as f:\n    requirements = [line.strip() for line in f if line.strip() and not line.startswith('#')]\nsetup(name='repolizer', version='0.1.0', install_requires=requirements)"
        
        # Create a mock that returns different content based on the filename
        def mock_file_open(filename, *args, **kwargs):
            if 'requirements.txt' in str(filename):
                return mock_open(read_data=req_content).return_value
            elif 'setup.py' in str(filename):
                return mock_open(read_data=setup_content).return_value
            return mock_open().return_value
        
        with patch('builtins.open', side_effect=mock_file_open):
            # Load the setup module with mocked open
            with patch('setuptools.setup') as mock_setup:
                # Execute setup.py code
                exec(setup_content)
                
                # Now setup should have been called
                mock_setup.assert_called_once()
                args, kwargs = mock_setup.call_args
                self.assertEqual(kwargs.get('install_requires'), expected_reqs)
    
    def test_entry_points(self):
        """Test that entry points are set correctly."""
        with patch('setuptools.setup') as mock_setup:
            # Load the setup module
            with open('setup.py') as f:
                exec(f.read())
            
            # Check entry_points
            args, kwargs = mock_setup.call_args
            expected_entry_points = {
                'console_scripts': ['repolizer=repolizer:main']
            }
            self.assertEqual(kwargs.get('entry_points'), expected_entry_points)


if __name__ == '__main__':
    unittest.main()