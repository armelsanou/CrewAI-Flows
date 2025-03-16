import asyncio
from langchain_ollama import OllamaLLM
from crewai import Agent, Task, Crew, Process
from crewai.flow.flow import Flow, start, listen, and_, or_
import sys
sys.stdout.reconfigure(encoding='utf-8')
import agentops
from agentops.event import Event
import os
os.environ["AGENTOPS_API_KEY"] = "492d3e4e-01a6-4298-b3f3-99b6257c9c3a"

# Initialiser AgentOps
agentops.init(os.getenv("AGENTOPS_API_KEY"), auto_start_session=False)

#session = agentops.start_session(tags=["data_processing"])

# Configuration du modèle LLM via Ollama
ollama_llm = OllamaLLM(
    model="ollama/llama3.2:3b" #you can use any other model downloaded using ollama pull model-name
    #base_url="http://localhost:11434"
)


# Définition des agents avec Ollama
dataValidationAgent = Agent(
    role='Data Validator',
    goal='Validate incoming data to ensure it meets predefined criteria. '
         'Give output only as "success" or "failure". If failure, provide the reason.',
    backstory="You verify data quality based on predefined rules.",
    llm=ollama_llm,
    verbose=True
)

dataBackupAgent = Agent(
    role='Data Backup Agent',
    goal='Securely create a backup of necessary data for recovery and safety.',
    backstory="You identify what needs to be backed up and ensure its security.",
    llm=ollama_llm,
    verbose=True
)

dataAnalysisAgent = Agent(
    role='Data Analyst',
    goal='Analyze data and generate meaningful insights relevant to the business.',
    backstory="You are skilled in data analysis and extracting necessary information.",
    llm=ollama_llm,
    verbose=True
)

notificationAgent = Agent(
    role='Notifier',
    goal='Generate notifications based on various outcomes with necessary information only.',
    backstory="You deliver alerts and updates efficiently.",
    llm=ollama_llm,
    verbose=True
)

# Définition du workflow avec CrewAI
class CustomDataFlow(Flow):

    def __init__(self, data):
        super().__init__()
        self.state['data'] = data
        self.state['validation_success'] = False
        self.state['analysis_success'] = False
        self.state['backup_done'] = False

    @start()
    async def validate_data(self):
        """Valide les données selon des critères définis."""

        #event = Event("data_validation_started", {"step": "validation", "status": "in_progress"})

        #event = Event("data_validation_started")
        #agentops.record(event)
        
        data = self.state['data']

        task_validate = Task(
            description=f'Validate the following data: {data}. Ensure score > 20 and age > 0',
            agent=dataValidationAgent,
            expected_output="success or failure"
        )

        crew = Crew(
            agents=[dataValidationAgent],
            tasks=[task_validate],
            verbose=True,
            process=Process.sequential
        )

        result = await crew.kickoff_async()
        self.state['validation_success'] = result.raw.strip().lower() == 'success'

        #event = Event("data_validation_succes")

        # Enregistrement de l'événement
        #agentops.record(event)

    @listen((validate_data))
    async def send_notification_on_failure(self):
        """Envoie une notification si la validation échoue."""
        
        if not self.state['validation_success']:
            task_notify = Task(
                description=f'Issue a notification for validation failure for data: {self.state["data"]}.',
                agent=notificationAgent,
                expected_output='Notification sent for validation failure'
            )

            crew = Crew(
                agents=[notificationAgent],
                tasks=[task_notify],
                verbose=True,
                process=Process.sequential
            )
            await crew.kickoff_async()
            print("Notification sent: Validation failed.")
        else:
            print("Validation succeeded, no notification for failure needed.")

    @listen((validate_data))
    async def analyze_data(self):
        """Analyse les données si la validation est réussie."""
        if self.state['validation_success']:

            #event = Event("data_analysis_started", {"step": "Analysis", "status": "in_progress"})
            #agentops.record(event)

            task_analyze = Task(
                description=f'Analyze validated data: {self.state["data"]} to extract meaningful insights.',
                agent=dataAnalysisAgent,
                expected_output='Data analysis completed successfully'
            )

            crew = Crew(
                agents=[dataAnalysisAgent],
                tasks=[task_analyze],
                verbose=True,
                process=Process.sequential
            )

            analysis_result = await crew.kickoff_async()
            self.state['analysis_success'] = analysis_result.raw.strip() == 'Data analysis completed successfully'
            
            #event = Event("data_analysis_succes", {"step": "analysis", "status": "success"})

            # Enregistrement de l'événement
            #agentops.record(event)

        else:
            print("Skipping analysis as data validation did not succeed.")

    @listen(and_(analyze_data, validate_data))
    async def backup_data(self):
        """Sauvegarde les données après une analyse réussie."""
        if self.state['analysis_success']:


            #event = Event("data_backup_started", {"step": "Backup", "status": "in_progress"})
            #agentops.record(event)

            task_backup = Task(
                description=f'Create a backup for analyzed data: {self.state["data"]}.',
                agent=dataBackupAgent,
                expected_output='Data backup completed successfully'
            )

            crew = Crew(
                agents=[dataBackupAgent],
                tasks=[task_backup],
                verbose=True,
                process=Process.sequential
            )

            backup_status = await crew.kickoff_async()
            self.state['backup_done'] = backup_status.raw.strip() == 'Data backup completed successfully'

            print("Data backup completed.")
            
            #event = Event("data_backup_succes", {"step": "Backup", "status": "success"})

            # Enregistrement de l'événement
            #agentops.record(event)
        else:
            print("Backup skipped as data analysis was not successful.")

    @listen(or_(send_notification_on_failure, backup_data))
    async def send_final_notification(self):
        """Envoie une notification finale résumant le traitement des données."""
        if not self.state['validation_success']:
            message = "Data validation failed. No backup needed."
        elif self.state['backup_done']:
            message = "Data successfully analyzed and backed up. Final notification issued."
        else:
            message = "Data processing completed with warnings."

        task_notify = Task(
            description=f'Issue final notification: {message} for data: {self.state["data"]}.',
            agent=notificationAgent,
            expected_output=f'Final notification sent: {message}'
        )

        crew = Crew(
            agents=[notificationAgent],
            tasks=[task_notify],
            verbose=True,
            process=Process.sequential
        )

        await crew.kickoff_async()
        print("Final notification sent.")
            
        #event = Event("data_notification_succes", {"step": "notification", "status": "success"})

        # Enregistrement de l'événement
        #agentops.record(event)

# Point d'entrée principal
async def main():
    data_flow = CustomDataFlow(data=
        {
            "id": 1,
            "name": "Armel",
            "age": int(50),
            "country": "FRANCE",
            "score": int(90),
            "status": "active"
        })
    data_flow.plot()  # Visualisation du workflow
    await data_flow.kickoff_async()

if __name__ == "__main__":
    asyncio.run(main())