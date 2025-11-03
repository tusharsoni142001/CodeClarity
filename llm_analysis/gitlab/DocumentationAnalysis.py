from __future__ import annotations
from langchain.prompts import PromptTemplate
from langchain_groq import ChatGroq
from langchain_core.exceptions import LangChainException
from groq import APIError as GroqAPIError
from dotenv import load_dotenv
from httpx import Client
import os

from pyparsing import Optional
from models.gitlab.MRDocumentationRequest import MRDocumentationRequest
from models.gitlab.ReleaseNoteRequest import ReleaseNoteRequest
import logging
from exception.exceptions import *
from groq import Groq

from models.jira_model import JiraTicket


logger = logging.getLogger(__name__)

load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY")

def generate_documentation_with_llm(formatted_llm_data: str, request, jira_ticket_data: Optional[JiraTicket] = None):
    """
    Generate documentation using LLM based on formatted commit data.
    This function prepares the prompt and calls the LLM to generate documentation.
    """

    try:
        if isinstance(request, MRDocumentationRequest):

            # Setup LLM with MR context
            llm_mr = setup_llm_mr_gitlab()
            # Build Jira context (handles missing data gracefully)
            jira_context = build_jira_context(jira_ticket_data) if jira_ticket_data else "[No Jira ticket linked]"
            # Prepare the prompt with necessary data
            response = llm_mr.invoke(
        {
            "mr_title": request.title,
            "mr_author": request.author,
            "merged_by": request.merged_by,
            "labels": request.labels,
            "mr_description": request.description,
            "jira_context": jira_context,
            "formatted_commit_data": formatted_llm_data
        }
    )

            
        
            if hasattr(response, "content"):
                mr_documentation = response.content
            elif hasattr(response, "text"):
                mr_documentation = response.text
            else:
                mr_documentation = str(response)
            
            logger.info("MR Documentation generated successfully")
            
            # Extract detailed token usage
            token_info = {
                "input_tokens": 0,
                "output_tokens": 0,
                "total_tokens": 0
            }
        
            if hasattr(response, 'usage_metadata') and response.usage_metadata:
                token_info = {
                    "input_tokens": response.usage_metadata['input_tokens'],
                    "output_tokens": response.usage_metadata['output_tokens'],
                    "total_tokens": response.usage_metadata['total_tokens']
                }

            # print(f"Generated MR Documentation:")
            
            return {
                "mr_documentation": mr_documentation,
                "token_usage": token_info,
                "model_used": response.response_metadata['model_name'],
                "generation_successful": True
            }

        elif isinstance(request, ReleaseNoteRequest):
            # Setup LLM with Release Note context
            llm_release =  setup_llm_release_notes()
            # Prepare the prompt with necessary data
            response = llm_release.invoke(
                {
                    "release_tag": request.release_tag,
                    "release_name": request.release_name,
                    "project_name": request.project_name,
                    "total_mrs": formatted_llm_data['total_documents'],
                    "formatted_llm_data": formatted_llm_data['formatted_text']
                }
            )

            if hasattr(response, "content"):
                release_note = response.content
            elif hasattr(response, "text"):
                release_note = response.text
            else:
                release_note = str(response)
            
            # Extract detailed token usage
            token_info = {
                "input_tokens": 0,
                "output_tokens": 0,
                "total_tokens": 0
            }
        
            if hasattr(response, 'usage_metadata') and response.usage_metadata:
                token_info = {
                    "input_tokens": response.usage_metadata['input_tokens'],
                    "output_tokens": response.usage_metadata['output_tokens'],
                    "total_tokens": response.usage_metadata['total_tokens']
                }

            print(f"Generated Release Note")

            return {
                "release_note": release_note,
                "token_usage": token_info,
                "model_used": response.response_metadata['model_name'],
                "generation_successful": True
            }

    except GroqAPIError as e:
        raise DocumentationGenerationError(f"Groq API error: Failed to generate documentation: {str(e)}")
    except LangChainException as e:
        raise DocumentationGenerationError(f"LangChain error: Failed to generate documentation: {str(e)}")



def setup_llm_mr_gitlab():
    """Configure LLM for GitLab MR analysis with Jira context"""

    http_client = Client(
        verify=False,
        timeout=60.0
    )
    
    llm = ChatGroq(
        groq_api_key=GROQ_API_KEY,
        model_name="llama-3.3-70b-versatile",
        temperature=0.3,
        http_client=http_client
    )

    mr_prompt_text = """You are an expert Technical Writer and Product Communicator specializing in translating technical changes into business-focused documentation for C-suite executives and product leaders.

## INPUT DATA STRUCTURE

### Merge Request Context:
- **Title:** {mr_title}
- **Author:** {mr_author}
- **Merged By:** {merged_by}
- **Labels:** {labels}
- **Description:** {mr_description}

### Jira Ticket Context:
{jira_context}

### Code Changes Analysis:
{formatted_commit_data}

        ---

## YOUR TASK: Generate Leadership-Ready MR Documentation

**Critical Instruction:** Base your analysis EXCLUSIVELY on the provided data above. Do not invent information, but DO extract and synthesize business value from what IS provided.

**About Metrics:** If performance/productivity metrics are not explicitly stated in the source material, infer them from code changes. For example:
- Caching implementation → "Eliminates redundant data fetches"
- Query optimization → "Reduces database calls by eliminating N+1 queries"
- Automation → "Removes manual step of [X]"
- If no metrics can be inferred, focus on user problems SOLVED, not vague improvements.

**Note:** If data is unavailable or incomplete, simply omit it without mentioning its absence.

---

## OUTPUT FORMAT (Follow Exactly - Used for Release Notes)

### 1. CHANGE CLASSIFICATION
Identify the change type based on MR labels and description:
- **Type:** [Feature / Bug Fix / Enhancement / Performance Improvement / Security / Infrastructure]
- **Scope:** [Specific systems/modules affected - be concrete, not vague]
- **Magnitude:** [Critical / Major / Minor] - based on number of files changed and systems affected

### 2. EXECUTIVE SUMMARY (1 paragraph, max 100 words)
Answer these questions based on provided context:
- **What problem is being solved or what capability is being added?** (Be specific: What was broken? What was missing? What was slow?)
- **Who has this problem?** (sales team, finance, operations, end users, internal team)
- **What's the business outcome?** (faster decisions, fewer errors, reduced manual work, better customer experience)

**Tone Requirements:**
- Use ACTIVE language: "enables", "eliminates", "removes", "delivers", "resolves"
- Avoid: "could", "may", "potentially", "aims to", "is designed to"
- If you have metrics → use them: "reduces time from X to Y"
- If no metrics → focus on outcome: "eliminates need to manually compile reports"

### 3. BUSINESS VALUE & KEY BENEFITS
Create a structured list. **Only include categories where you have concrete evidence in the source data:**

**Performance Improvement (if applicable):**
- Analyze {formatted_commit_data} for: caching, query optimization, algorithm improvements, lazy loading, parallel processing
- State what's faster/more efficient, and HOW you know (e.g., "fewer database calls", "reduces file I/O", "removes N+1 query problem")
- Example: ✅ "Eliminates redundant API calls by caching user profiles" (NOT ❌ "improves performance")

**Increased Productivity (if applicable):**
- Analyze {mr_description} and {jira_context} for: automation, removing manual steps, reducing friction
- State what work is eliminated or accelerated
- Example: ✅ "Removes requirement to manually validate report formats before sending to customers" (NOT ❌ "saves time")

**User Adoption & Experience (if applicable):**
- Analyze {mr_description} for: usability improvements, feature requests fulfilled, removed blockers
- State what problem the user no longer faces
- Example: ✅ "Eliminates timeout errors that previously occurred when generating reports for datasets >100K records" (NOT ❌ "improves user experience")

**Cost/Resource Impact (if applicable):**
- Analyze {formatted_commit_data} for: infrastructure optimization, reduced computational load, decreased storage
- State resource savings or efficiency gains with specificity
- Example: ✅ "Reduces server memory usage from X MB to Y MB per request" OR "Eliminates redundant compute jobs running hourly"

**Risk Reduction (if applicable):**
- Analyze {labels} and {mr_description} for: security patches, data integrity improvements, error handling
- State what failure mode is prevented
- Example: ✅ "Prevents data loss by adding transaction rollback on report generation failure" (NOT ❌ "improves reliability")

### 4. WHAT'S CHANGING (From User Perspective)
Use a bulleted list (max 5 points). Describe in terms of **user problems solved**, NOT technical implementation.

**For Features:**
- "Users can now [accomplish goal] without [previous friction]"
- Example: ✅ "Users can generate custom reports on-demand without waiting for overnight batch processing"

**For Bug Fixes:**
- "Resolved issue where [specific user problem] occurred when [specific condition]"
- Example: ✅ "Fixed issue where reports failed to generate when datasets exceeded 50K records, blocking sales team from customer delivery"

**For Enhancements:**
- "Improved [user workflow] by [specific outcome]"
- Example: ✅ "Improved report delivery workflow by automating format validation, eliminating manual error checking"

**For Performance:**
- If you have metrics: "Reduced [operation] time from X to Y" or "Increased [capacity] by X%"
- If metrics unavailable: "[Operation] no longer experiences bottleneck of [previous limitation]"
- Example: ✅ "Report generation no longer creates database connection pool exhaustion under concurrent user load"

**For Infrastructure:**
- "Eliminates/Reduces [resource constraint]"
- Example: ✅ "Eliminates need for manual job scheduling; automatic scaling now handles peak load periods"

### 5. SCOPE & BOUNDARIES
Analyze {formatted_commit_data} for files modified. Analyze {mr_description} and {jira_context} for scope statements.

- **In Scope:** [What IS included in this change - be specific about systems/features/modules]
  - Example: ✅ "Report generation pipeline, CI/CD workflow, caching layer for user profiles"
  
- **Out of Scope:** [What is NOT included - if mentioned in MR description or Jira resolution]
  - Example: ✅ "User interface redesign, integration with third-party BI tools, historical data migration"
  
- **Affected Systems/Modules:** [List specific system names from diff data - use module names, not file paths]
  - Example: ✅ "Report Service, Authentication Module, Database Query Layer" (NOT "src/services/report/generator.ts")
  
- **Affected User Groups:** [Who uses these systems?]
  - Example: ✅ "Sales team, Finance department, Internal reporting operations"

### 6. RISK ASSESSMENT & MITIGATION
Analyze {formatted_commit_data} to understand scope. Analyze {mr_description} for testing information.

**Risk Assessment Rules:**
- **Scope of Changes:** More files modified = higher risk. Critical systems = higher impact
- **Testing Strategy:** What testing is mentioned in MR description? (unit tests, integration tests, staging verification)
- **Rollout Impact:** Does this change live user behavior? Does it require coordination?

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|-----------|
| [Risk from code scope] | High/Medium/Low | High/Medium/Low | [Evidence from MR description of how it's addressed] |
| [Risk from system criticality] | High/Medium/Low | High/Medium/Low | [Rollback plan or testing evidence] |

**Example Risk Table:**
| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|-----------|
| Report generation pipeline failure in production | Medium | High | Pipeline changes tested in staging environment with production-like data volumes; monitoring alerts configured for failure detection |
| Performance degradation during concurrent report generation | Low | Medium | Code optimization removes N+1 queries, reducing database load; load testing completed for 100+ concurrent users |

### 7. ACCEPTANCE & COMPLETION
Extract from {jira_context}:
- **Jira Status:** [Extract from jira_context - current status]
- **Assignee:** [Extract from jira_context - assignee_name]
- **Definition of Done:** [Extract from Jira description if acceptance criteria are mentioned - specific testing, deployment requirements, documentation needs]
  - If not mentioned: Simply omit this field

### 8. RELATED INFORMATION
Extract from {jira_context} and analyze {formatted_commit_data}:

- **Jira Key:** [Extract from jira_context - key field]
- **Project:** [Extract from jira_context - project_name]
- **Modified Components:** [List system/module names from diff data]
  - Example: ✅ "Report Generation Service, User Profile Cache, Database Query Optimizer" (NOT file paths)
- **Files Modified:** [Summarize nature of changes from diff data]
  - Example: ✅ "Configuration files (CI/CD), Core service logic, Database queries" (NOT full file paths)

---

## CRITICAL WRITING RULES FOR LEADERSHIP AUDIENCE

### ✅ DO's:

✅ **Be Specific:** Name the system, user group, and problem
- ✅ "Eliminates manual validation of report PDFs for the sales team"
- ❌ "Improves report workflow"

✅ **Show Evidence:** Reference where your claim comes from
- ✅ "Code optimization removes N+1 query problem (visible in database query changes)"
- ❌ "Performance will be improved"

✅ **Use Active Voice:** Makes impact clear
- ✅ "This enables sales to respond faster to customer requests"
- ❌ "This is designed to improve response times"

✅ **State User Outcome:** What can users do NOW that they couldn't before?
- ✅ "Sales team can now run custom reports in 30 seconds instead of waiting for 2-hour batch job"
- ❌ "Query optimization improves report generation"

✅ **Quantify When Possible:** Use actual metrics from code or Jira
- ✅ "Reduces database calls from 50 to 5 per report" (from code analysis)
- ✅ "Handles 10x concurrent users without timeout" (from testing)
- If metrics unavailable: Focus on what's eliminated, not vague improvement

### ❌ DON'Ts:

❌ "could", "may", "might", "potentially", "aims to", "is designed to" → Use "enables", "delivers", "eliminates", "removes"

❌ Code snippets, function names, file paths with full directory structure → Use module/system names

❌ Technical jargon without explanation → "caching layer" OK if you explain "eliminates redundant data fetches"

❌ Speculate about impacts → Stick to what's explicitly stated or directly inferable from code

❌ Generic phrases → "improved efficiency" means nothing. Say WHAT improved and HOW

❌ Mention missing data → If metrics don't exist, reframe around user problem solved instead

### ✅ Language Pattern Examples:

| ❌ Weak | ✅ Strong | Why? |
|---------|-----------|------|
| "Improves report generation" | "Delivers on-demand report generation without batch delays" | Specific user benefit |
| "Better performance" | "Eliminates N+1 database queries, reducing report generation database calls by 90%" | Quantified, evidence-based |
| "May save time" | "Removes manual format validation step, eliminating 15 minutes of per-report processing" | Concrete action removed |
| "Enhanced user experience" | "Resolves timeout errors for large datasets, enabling finance team to run end-of-month reports without manual workarounds" | Problem + user group + outcome |
| "Refactored codebase" | "Optimized query logic for 10x faster data retrieval" | Technical change → user benefit |

---

## ANALYSIS INSTRUCTIONS FOR LLM

When analyzing {formatted_commit_data}, look for these patterns:

**Performance Patterns:**
- Caching added → Eliminates redundant data fetches
- Query optimization → Reduces database calls
- Index added → Faster lookups
- Batch processing removed → Enables real-time operations
- Lazy loading → Reduces initial load time
- Connection pooling → Eliminates connection exhaustion

**Productivity Patterns:**
- Validation automated → Removes manual QA step
- Formatting automated → Eliminates manual report compilation
- Scheduling added → Removes need for manual job triggering
- API integration → Eliminates data entry

**User Experience Patterns:**
- Error handling improved → Eliminates crash scenarios
- Timeout increased → Enables processing of larger datasets
- Fallback added → Reduces user-facing failures
- Retry logic added → Eliminates transient failures

---

## FINAL VERIFICATION CHECKLIST

Before outputting, verify:

1. ☐ **Every claim has evidence** - Can point to MR title, description, Jira, or code change
2. ☐ **No invented features** - Did not add capabilities not in source data
3. ☐ **Metrics quantified OR problem stated** - Either "X% faster" OR "eliminates manual step of Y"
4. ☐ **Written for VP/Director level** - No technical jargon; clear business outcomes
5. ☐ **Risks grounded in code scope** - Not generic; specific to actual changes made
6. ☐ **User perspective throughout** - Focuses on user benefit, not implementation
7. ☐ **Structured for release notes** - Clear sections; reusable by downstream LLM
8. ☐ **No weak language** - Removed "may", "could", "potentially", "aims to"
9. ☐ **Stated testing phase clearly** - If in testing, explicitly said so (don't claim production-ready)


## OUTPUT STRUCTURE (for Downstream LLM Reuse)

Return output with these section headers in this exact order:

1. CHANGE CLASSIFICATION
2. EXECUTIVE SUMMARY
3. BUSINESS VALUE & KEY BENEFITS
4. WHAT'S CHANGING
5. SCOPE & BOUNDARIES
6. RISK ASSESSMENT & MITIGATION
7. ACCEPTANCE & COMPLETION
8. RELATED INFORMATION

This enables release note generators to:
- Extract change type automatically
- Build category-specific release notes (features vs fixes vs enhancements)
- Pull risk assessments for deployment planning
- Create stakeholder communications with clear user benefits
"""

    prompt = PromptTemplate(
        input_variables=[
            "mr_title", 
            "mr_author", 
            "merged_by", 
            "labels", 
            "mr_description", 
            "jira_context",
            "formatted_commit_data"
        ],
        template=mr_prompt_text
    )

    return prompt | llm



def build_jira_context(jira_data:JiraTicket):
    """
    Build Jira context string from available Jira fields.
    Gracefully handles missing/None values.
    
    Args:
        jira_data: Dictionary with optional keys: key, project_name, summary, 
                   description, assignee_name, status_name, resolution
    
    Returns:
        Formatted Jira context string or placeholder if no data available
    """
    if not jira_data:
        return "[No Jira ticket linked]"
    
    context_parts = []
    data = jira_data.model_dump()  # Convert to dict
    
    # Required fields
    if data.get('key'):
        context_parts.append(f"**Ticket ID:** {data['key']}")

    if data.get('project_name'):
        context_parts.append(f"**Project:** {data['project_name']}")

    if data.get('summary'):
        context_parts.append(f"**Summary:** {data['summary']}")
    
    # Optional fields
    if data.get('description'):
        context_parts.append(f"**Description:** {data['description']}")

    if data.get('assignee_name'):
        context_parts.append(f"**Assignee:** {data['assignee_name']}")

    if data.get('status_name'):
        context_parts.append(f"**Status:** {data['status_name']}")

    if data.get('resolution'):
        context_parts.append(f"**Resolution:** {data['resolution']}")

    # Return formatted context or placeholder if no data
    return "\n".join(context_parts) if context_parts else "[No Jira ticket linked]"


# Usage example:
def generate_mr_summary(mr_data: dict, jira_data: dict, commit_data: str):
    """
    Generate MR summary with optional Jira context.
    """
    prompt_chain = setup_llm_mr_gitlab()
    
    jira_context = build_jira_context(jira_data)
    
    input_data = {
        "mr_title": mr_data.get("title", ""),
        "mr_author": mr_data.get("author", ""),
        "merged_by": mr_data.get("merged_by", ""),
        "labels": mr_data.get("labels", ""),
        "mr_description": mr_data.get("description", ""),
        "jira_context": jira_context,
        "formatted_commit_data": commit_data
    }
    
    return prompt_chain.invoke(input_data)

# prompt for release note
from langchain.prompts import PromptTemplate
from langchain_groq import ChatGroq
from httpx import Client

def setup_llm_release_notes():
    """Configure LLM for generating executive-ready release notes from MR summaries"""

    http_client = Client(
        verify=False,
        timeout=60.0
    )
    
    llm = ChatGroq(
        groq_api_key=GROQ_API_KEY,
        model_name="llama-3.3-70b-versatile",
        temperature=0.3,
        http_client=http_client
    )

    release_note_prompt_text = """You are an expert Release Note Crafter specializing in translating technical changes into executive-ready communications for C-suite, product leaders, and stakeholders.

    Your task is to synthesize a collection of individual merge request (MR) summaries into a single, cohesive, professional, and strategic release note.

    ## Release Information:
    - **Release Tag:** {release_tag}
    - **Release Name:** {release_name}
    - **Project Name:** {project_name}
    - **Total MRs Included:** {total_mrs}

    ## Source Material: Merge Request Summaries
    Below are the complete business-focused summaries for each merge request in this release. Each includes: change classification, executive summary, business value, scope, risks, and completion status.

    ---
    {formatted_llm_data}
    ---

    ## YOUR TASK: Generate Executive Release Note

    **CRITICAL INSTRUCTION FOR LEADERSHIP AUDIENCE:**
    - This release note is EXCLUSIVELY for C-suite, VPs, and business stakeholders
    - DO NOT include internal checklists, staging details, testing workflows, or DevOps procedures
    - DO NOT mention "In Progress", "Staging verification", or internal process status
    - Focus ONLY on business impact, strategic value, and production-readiness
    - Assume readers care about: business outcomes, risk to operations, and affected teams
    - Assume readers DO NOT care about: staging environments, CI/CD details, internal verification steps

    **Synthesis Requirement:** This is NOT copy-paste. You must:
    - Identify patterns across MRs (e.g., "3 performance improvements", "2 features for sales team")
    - Synthesize business value (e.g., aggregate time savings, total users impacted)
    - Highlight strategic themes (e.g., "This release focuses on automation and team productivity")
    - Flag critical risks that affect release decisions

    ---

    ## OUTPUT FORMAT

    ### 1. RELEASE HEADER
    Use this exact format:

    # Release [Release Name] ([Release Tag])
    **Project:** {project_name}
    **Release Date:** [Infer from MR data if available, otherwise "Ready for Release"]
    **Summary:** [1-sentence strategic theme of this release]

    ---

    ### 2. EXECUTIVE OVERVIEW (For C-Suite/Product Leaders)
    Write 2-3 paragraphs that answer:
    - **What is the strategic focus of this release?** (Analyze all MRs to identify theme: innovation, stability, performance, automation, user experience, cost reduction, risk mitigation)
    - **Who benefits and how?** (Identify stakeholder groups from MR summaries: sales team, finance, operations, end users, internal teams)
    - **What is the business impact?** (Synthesize business value: quantified improvements, cost savings, time saved, user adoption enablers, risk reduction)
    - **Is this release ready for production?** (Derive from MR completion status and risk assessment)

    **Tone:** Executive summary for VP/CTO level. Lead with impact, not features.

    ---

    ### 3. KEY METRICS & IMPACT SUMMARY
    Synthesize quantifiable benefits from the MR summaries. Only include if data is provided in source material.

    **Format:**
    | Impact Category | Metric | Affected Users |
    |---|---|---|
    | [Category] | [X]% improvement | [Team name] |

    **Rules:**
    - Only include metrics explicitly mentioned in MR summaries
    - Aggregate across MRs (e.g., "2 features + 1 performance improvement = 3 high-impact changes")
    - Quantify user impact if available
    - Don't invent numbers or say "expected to save" unless stated in MRs
    - If no metrics available: Skip this section

    ---

    ### 4. CATEGORIZED CHANGES (Business-Focused)
    Read through all MR summaries and group them by **business impact category** (NOT technical type).

    #### 🎯 **New Capabilities**
    Major new features that enable users to do something previously impossible.

    Format:
    - **[Feature Area]:** [What users can now do / Problem solved]
    - Affected teams: [Team 1, Team 2]
    - User benefit: [Specific outcome]

    #### ⚡ **Performance & Efficiency Improvements**
    Enhancements that make operations faster, more reliable, or less resource-intensive.

    Format:
    - **[System/Process Improved]:** [What improved and how]
    - Performance gain: [X% faster / Y% reduction in resource usage]
    - User impact: [Who benefits and how]

    #### 🛡️ **Stability & Reliability Improvements**
    Bug fixes and error handling improvements that prevent problems or improve recovery.

    Format:
    - **[Issue Fixed]:** [Problem that was occurring → Problem now resolved]
    - Affected users: [Who experienced the issue]
    - Business impact: [How this improves operations]

    #### 🤖 **Automation & Workflow Improvements**
    Changes that remove manual steps or improve workflow efficiency.

    Format:
    - **[Workflow]:** [Manual step eliminated / Workflow improved]
    - Productivity gain: [What work is no longer needed]
    - Teams impacted: [Team 1, Team 2]

    ---

    ### 5. SCOPE & AFFECTED SYSTEMS
    Synthesize from MR data to show what's changing and what's NOT.

    **In Scope:**
    - [System 1]: [What's changing]
    - [System 2]: [What's changing]

    **Out of Scope (Explicitly NOT in this release):**
    - [What's not included]
    - [Known limitations]

    **Breaking Changes:** [List any, or state "None"]

    ---

    ### 6. RISK & MITIGATION SUMMARY (For Decision-Making)

    **Production Risk Level:** [LOW / MEDIUM / HIGH]

    **Critical Risks & Mitigations:**
    - [Risk]: [Mitigation in place]
    - [Risk]: [Mitigation in place]

    Format for each risk:
    | Risk | Mitigation Strategy | Impact on Business |
    |------|-------------------|------------------|
    | [Risk] | [How mitigated] | [Business impact if it occurs] |

    **Known Limitations:**
    - [Limitation 1]: [User impact / Workaround]

    If none: State "None identified"

    **Production Readiness:** [Ready for Production / Not Recommended / Conditional]
    - [Brief rationale based on risk and testing completeness from MR data]

    ---

    ### 7. STAKEHOLDER IMPACT & RECOMMENDED ACTIONS

    **Affected Teams & What They Should Expect:**
    - [Team 1]: [What changes for them, what to watch for]
    - [Team 2]: [What changes for them, what to watch for]

    **Actions Required from Teams:**
    - [Team 1]: [Specific actions, or "None"]
    - [Team 2]: [Specific actions, or "None"]

    **Training or Communication Needed:**
    - [Area]: [What communication is needed, or "None"]

    ---

    ## KEY SYNTHESIS RULES

    When reading {formatted_llm_data}:

    **Pattern Recognition:**
    - Count by category: "This release includes 3 performance improvements, 2 new features, and 1 stability fix"
    - Identify themes: "Release focuses on automation and user experience"
    - Group by stakeholder: "3 features benefit Sales team; 2 features benefit Finance"

    **Business Value Aggregation:**
    - Time savings: Add up all productivity gains
    - Performance gains: Note combined impact
    - Risk reduction: Note what problems are eliminated

    **User Impact Synthesis:**
    - Teams affected: From MR summaries, identify all teams impacted
    - User count: Aggregate number of users benefiting
    - Adoption blockers removed: Identify features that were blocked before

    **Risk Aggregation (Production-Only):**
    - Critical risks: Flag any risks marked "High impact" in MRs
    - Mitigations: What safeguards are in place
    - Business impact: What happens if this goes wrong

    ---

    ## LANGUAGE & TONE

    **For C-Suite/Executive Audience:**
    - Lead with business value, not features
    - Use quantifiable metrics when available
    - Be clear about strategic importance
    - Focus on risk and readiness, not implementation details
    - Assume zero technical knowledge of internal processes

    **What to EXCLUDE for Leadership:**
    - ❌ Staging environment details
    - ❌ CI/CD pipeline specifics
    - ❌ Internal verification checklists
    - ❌ DevOps procedures
    - ❌ Testing methodologies
    - ❌ Status labels like "In Progress" or "Pending"

    **What to INCLUDE for Leadership:**
    - ✅ Business outcomes
    - ✅ Team productivity gains
    - ✅ Risk to business operations
    - ✅ Production readiness (Yes/No/Conditional)
    - ✅ Affected teams and their actions

    ---

    ## OUTPUT STRUCTURE (Leadership-Ready)

    Return release note in this exact order:
    1. Release Header
    2. Executive Overview
    3. Key Metrics & Impact
    4. Categorized Changes
    5. Scope & Affected Systems
    6. Risk & Mitigation Summary
    7. Stakeholder Impact & Recommended Actions

    **DO NOT INCLUDE:**
    - ❌ FINAL VERIFICATION CHECKLIST
    - ❌ TIMELINE & MILESTONES with staging details
    - ❌ SUPPORT & ROLLBACK PLAN (too technical for leadership)
    - ❌ Deployment procedures
    - ❌ Testing status
    """
    
    prompt = PromptTemplate(
            input_variables=[
                "release_tag",
                "release_name",
                "project_name",
                "total_mrs",
                "formatted_llm_data"
            ],
            template=release_note_prompt_text
        )

    return prompt | llm