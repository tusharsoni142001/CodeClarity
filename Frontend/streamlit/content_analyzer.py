import re
from typing import Dict, List, Optional
from datetime import datetime
from mr_utils import count_mrs_in_release

class ContentAnalyzer:
    """
    Advanced content analysis class for release notes and documentation.
    Designed to be easily extensible for future analysis needs.
    """
    
    def __init__(self):
        self.project_keywords = {
            'library_management': ['library', 'book', 'catalog', 'circulation', 'patron'],
            'general_features': ['feature', 'functionality', 'capability', 'module', 'component'],
            'improvements': ['improvement', 'enhancement', 'optimize', 'performance', 'upgrade', 'refactor'],
            'changes': ['change', 'update', 'modify', 'fix', 'bug', 'issue', 'patch'],
            'technical': ['api', 'database', 'service', 'class', 'method', 'function']
        }
    
    def analyze_release_content(self, content: str, release_version: str) -> Dict:
        """
        Comprehensive analysis of release content with project-specific insights.
        
        Args:
            content: The release notes content
            release_version: Version string (e.g., 'v2.6')
            
        Returns:
            Dictionary containing analysis results
        """
        if not content:
            return self._empty_analysis()
        
        analysis = {
            'title': self._extract_title(content),
            'summary': self._extract_summary(content),
            'features_count': self._count_features(content),
            'improvements_count': self._count_improvements(content),
            'changes_count': self._count_changes(content),
            'mr_count': count_mrs_in_release(release_version),
            'project_name': self._extract_project_name(content),
            'release_date': self._extract_release_date(content),
            'technical_highlights': self._extract_technical_highlights(content),
            'complexity_score': self._calculate_complexity_score(content),
            'release_type': self._determine_release_type(release_version, content)
        }
        
        return analysis
    
    def _extract_title(self, content: str) -> str:
        """Extract the main title from content"""
        lines = content.split('\n')
        for line in lines:
            if line.strip().startswith('#') and len(line.strip()) > 1:
                return re.sub(r'^#+\s*', '', line.strip())
        return "Release Documentation"
    
    def _extract_summary(self, content: str) -> str:
        """Extract the first substantial paragraph as summary"""
        lines = content.split('\n')
        for line in lines:
            stripped = line.strip()
            if (len(stripped) > 50 and 
                not stripped.startswith('#') and 
                not stripped.startswith('-') and 
                not stripped.startswith('*') and
                not stripped.startswith('>')):
                return stripped
        return "This release introduces enhancements to the system functionality and user experience."
    
    def _count_features(self, content: str) -> int:
        """Count new features mentioned in content"""
        content_lower = content.lower()
        patterns = [
            r'new\s+(feature|functionality|capability|module)',
            r'introduce[sd]?\s+.*?(feature|functionality|capability)',
            r'add[ed]?\s+.*?(feature|functionality|capability)',
            r'implement[ed]?\s+.*?(feature|functionality|capability)'
        ]
        
        count = 0
        for pattern in patterns:
            count += len(re.findall(pattern, content_lower))
        
        # Also count bullet points under "features" sections
        count += self._count_section_items(content, ['new features', 'features', 'additions'])
        
        return max(count, 1)  # Ensure at least 1 for any release
    
    def _count_improvements(self, content: str) -> int:
        """Count improvements mentioned in content"""
        content_lower = content.lower()
        improvement_keywords = '|'.join(self.project_keywords['improvements'])
        pattern = rf'\b({improvement_keywords})\b'
        
        count = len(re.findall(pattern, content_lower))
        count += self._count_section_items(content, ['improvements', 'enhancements', 'optimizations'])
        
        return count
    
    def _count_changes(self, content: str) -> int:
        """Count total changes mentioned in content"""
        content_lower = content.lower()
        change_keywords = '|'.join(self.project_keywords['changes'])
        pattern = rf'\b({change_keywords})\b'
        
        count = len(re.findall(pattern, content_lower))
        count += self._count_section_items(content, ['changes', 'updates', 'fixes', 'bug fixes'])
        
        return count
    
    def _count_section_items(self, content: str, section_names: List[str]) -> int:
        """Count items in specific sections"""
        content_lower = content.lower()
        count = 0
        
        for section_name in section_names:
            # Find section headers
            section_pattern = rf'#+\s*{re.escape(section_name)}'
            section_match = re.search(section_pattern, content_lower)
            
            if section_match:
                # Find content after the section header until next header
                start_pos = section_match.end()
                next_header = re.search(r'\n#+\s', content_lower[start_pos:])
                
                if next_header:
                    section_content = content_lower[start_pos:start_pos + next_header.start()]
                else:
                    section_content = content_lower[start_pos:]
                
                # Count bullet points and numbered items
                bullet_points = len(re.findall(r'\n\s*[-*•]\s+', section_content))
                numbered_items = len(re.findall(r'\n\s*\d+\.\s+', section_content))
                
                count += bullet_points + numbered_items
        
        return count
    
    def _extract_project_name(self, content: str) -> str:
        """Extract project name from content"""
        content_lower = content.lower()
        
        # Look for common project name patterns
        patterns = [
            r'(library\s+management\s+system)',
            r'(demo-project)',
            r'(\w+[-_]\w+)\s+(?:project|system|platform)',
            r'(?:project|system):\s*(\w+[-_\w]*)'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, content_lower)
            if match:
                return match.group(1).title().replace('_', ' ').replace('-', ' ')
        
        return "Library Management System"
    
    def _extract_release_date(self, content: str) -> str:
        """Extract release date from content"""
        # Look for date patterns
        date_patterns = [
            r'(january|february|march|april|may|june|july|august|september|october|november|december)\s+\d{1,2},?\s+\d{4}',
            r'\d{1,2}[/-]\d{1,2}[/-]\d{4}',
            r'\d{4}[/-]\d{1,2}[/-]\d{1,2}'
        ]
        
        for pattern in date_patterns:
            match = re.search(pattern, content, re.IGNORECASE)
            if match:
                return match.group(0)
        
        # Fallback to current date
        return datetime.now().strftime("%B %d, %Y")
    
    def _extract_technical_highlights(self, content: str) -> List[str]:
        """Extract technical highlights from content"""
        content_lower = content.lower()
        highlights = []
        
        # Look for technical terms and API mentions
        technical_keywords = self.project_keywords['technical']
        for keyword in technical_keywords:
            if keyword in content_lower:
                highlights.append(keyword.upper())
        
        # Look for code-related terms
        code_patterns = [
            r'\b(class|method|function|api|endpoint|service)\b',
            r'\b(database|sql|json|xml|rest)\b',
            r'\b(authentication|authorization|security)\b'
        ]
        
        for pattern in code_patterns:
            matches = re.findall(pattern, content_lower)
            highlights.extend([match.upper() for match in matches])
        
        return list(set(highlights))[:5]  # Return top 5 unique highlights
    
    def _calculate_complexity_score(self, content: str) -> str:
        """Calculate release complexity based on content analysis"""
        lines = len(content.split('\n'))
        words = len(content.split())
        
        # Simple scoring based on content length and technical terms
        technical_count = len(self._extract_technical_highlights(content))
        
        if words > 1000 or technical_count > 10:
            return "High"
        elif words > 500 or technical_count > 5:
            return "Medium"
        else:
            return "Low"
    
    def _determine_release_type(self, version: str, content: str) -> str:
        """Determine the type of release based on version and content"""
        content_lower = content.lower()
        
        # Major version pattern (x.0.0 or vx.0)
        if re.match(r'v?\d+\.0(?:\.0)?$', version):
            return "Major Release"
        
        # Minor version with significant features
        feature_count = self._count_features(content)
        if feature_count > 3:
            return "Feature Release"
        
        # Bug fix or patch release
        if any(keyword in content_lower for keyword in ['fix', 'bug', 'patch', 'hotfix']):
            return "Maintenance Release"
        
        return "Standard Release"
    
    def _empty_analysis(self) -> Dict:
        """Return empty analysis structure"""
        return {
            'title': "Release Documentation",
            'summary': "No content available for analysis.",
            'features_count': 0,
            'improvements_count': 0,
            'changes_count': 0,
            'mr_count': 0,
            'project_name': "Project",
            'release_date': datetime.now().strftime("%B %d, %Y"),
            'technical_highlights': [],
            'complexity_score': "Low",
            'release_type': "Unknown"
        }
    
    def analyze_mr_content(self, content: str, mr_info: Dict) -> Dict:
        """
        Analyze MR content for additional insights.
        This method can be extended for MR-specific analysis.
        """
        # Future implementation for MR analysis
        return {
            'type': self._determine_mr_type(content),
            'impact': self._assess_mr_impact(content),
            'files_changed': self._count_files_changed(content),
            'lines_changed': self._estimate_lines_changed(content)
        }
    
    def _determine_mr_type(self, content: str) -> str:
        """Determine MR type based on content"""
        content_lower = content.lower()
        
        if any(keyword in content_lower for keyword in ['feature', 'new', 'add']):
            return "Feature"
        elif any(keyword in content_lower for keyword in ['fix', 'bug', 'issue']):
            return "Bug Fix"
        elif any(keyword in content_lower for keyword in ['refactor', 'improve', 'optimize']):
            return "Improvement"
        else:
            return "Other"
    
    def _assess_mr_impact(self, content: str) -> str:
        """Assess the impact level of an MR"""
        # Simple impact assessment based on content
        words = len(content.split())
        
        if words > 500:
            return "High"
        elif words > 200:
            return "Medium"
        else:
            return "Low"
    
    def _count_files_changed(self, content: str) -> int:
        """Estimate number of files changed"""
        # Look for file mentions in content
        file_patterns = [
            r'\b\w+\.\w+\b',  # filename.extension
            r'\b\w+/\w+\b'    # path/file
        ]
        
        files = set()
        for pattern in file_patterns:
            matches = re.findall(pattern, content)
            files.update(matches)
        
        return len(files)
    
    def _estimate_lines_changed(self, content: str) -> str:
        """Estimate lines of code changed"""
        words = len(content.split())
        
        # Rough estimation based on content length
        if words > 300:
            return "100+"
        elif words > 150:
            return "50-100"
        else:
            return "<50"

# Global analyzer instance
analyzer = ContentAnalyzer()