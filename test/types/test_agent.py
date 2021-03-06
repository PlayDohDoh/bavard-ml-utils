from unittest import TestCase

from fastapi.encoders import jsonable_encoder

from bavard_ml_utils.types.agent import AgentConfig, AgentExport
from bavard_ml_utils.types.conversations.actions import UserAction
from bavard_ml_utils.types.conversations.conversation import Conversation
from bavard_ml_utils.types.conversations.dialogue_turns import UserDialogueTurn
from test.utils import load_json_file


class TestAgent(TestCase):
    def test_filters_bad_training_conversations(self):
        agent_config = AgentExport.parse_file("test/data/agents/test-agent.json").config

        # Empty conversations should be filtered out.
        num_convs = len(agent_config.trainingConversations)
        agent_config.trainingConversations.append(Conversation(turns=[]))
        self.assertEqual(len(agent_config.trainingConversations), num_convs + 1)
        agent_config = AgentConfig.parse_obj(jsonable_encoder(agent_config))
        agent_config.filter_no_agent_convs()

        # The added conversation should be filtered out.
        self.assertEqual(len(agent_config.trainingConversations), num_convs)

        # Conversations with no agent actions should be filtered out.
        agent_config.trainingConversations.append(
            Conversation(turns=[UserDialogueTurn(userAction=UserAction(type="UTTERANCE_ACTION"))])
        )
        self.assertEqual(len(agent_config.trainingConversations), num_convs + 1)
        agent_config.filter_no_agent_convs()
        # The added conversation should be filtered out.
        self.assertEqual(len(agent_config.trainingConversations), num_convs)

    def test_adds_nlu_examples_from_training_conversations(self):
        raw_agent = load_json_file("test/data/agents/bavard.json")["config"]
        n_nlu_examples = sum(len(examples) for examples in raw_agent["intentExamples"].values())
        agent = AgentConfig.parse_obj(raw_agent)
        agent.incorporate_training_conversations()
        # The `agent` object should now have more nlu examples than `n_nlu_examples`.
        self.assertGreater(len(list(agent.all_nlu_examples())), n_nlu_examples)

    def test_excludes_examples_with_unknown_labels(self):
        messy_agent = AgentExport.parse_file("test/data/agents/invalid-nlu-examples.json").config
        messy_agent.filter_invalid_intent_examples()

        # Examples with unregistered intents or tag types should be filtered out.
        self.assertEqual(len(list(messy_agent.all_nlu_examples())), 2)
        for ex in messy_agent.all_nlu_examples():
            self.assertIn(ex.intent, messy_agent.intent_names())
            for tag in ex.tags or []:
                self.assertIn(tag.tagType, messy_agent.tag_names())

    def test_no_side_effects_from_conversion(self):
        config = AgentExport.parse_file("test/data/agents/bavard.json").config
        snapshot = config.copy(deep=True)
        config.to_nlu_dataset()
        config.to_conversation_dataset()
        self.assertEqual(config, snapshot)

    def test_intent_ood_examples(self):
        config = AgentExport.parse_file("test/data/agents/ood.json").config
        n_ood = len(config.intentOODExamples)
        self.assertGreater(n_ood, 0)
        without_ood = config.to_nlu_dataset()
        dataset = config.to_nlu_dataset(include_ood=True)
        # All the ood examples should be included in `dataset`
        self.assertEqual(len(without_ood) + n_ood, len(dataset))
        self.assertEqual(sum(1 for ex in dataset if ex.isOOD), n_ood)
        # The dataset w/OOD examples should have an extra label: the `None` label.
        self.assertEqual(len(dataset.unique_labels()), len(without_ood.unique_labels()) + 1)
        self.assertIn(None, dataset.unique_labels())
        self.assertNotIn(None, without_ood.unique_labels())

    def test_conversation_dataset_conversion(self):
        config = AgentExport.parse_file("test/data/agents/bavard.json").config
        config.clean()
        convs = config.to_conversation_dataset(expand=False)
        reconstructed = AgentConfig.from_conversation_dataset(convs, name=config.name)
        # The reconstructed agent should have the same conversation data.
        self.assertEqual(len(config.trainingConversations), len(reconstructed.trainingConversations))
        self.assertTrue(reconstructed.intent_names().issubset(config.intent_names()))
        self.assertSetEqual(config.action_names(), reconstructed.action_names())
        for i in range(len(config.trainingConversations)):
            self.assertEqual(config.trainingConversations[i], reconstructed.trainingConversations[i])

        # The conversion process should allow training conversations which have user utterances with no intents
        config = AgentExport.parse_file("test/data/agents/no-intents-in-convs.json").config
        convs = config.to_conversation_dataset(expand=False)
        self.assertEqual(len(config.trainingConversations), len(convs))  # no convs should have been lost
        for config_conv, dataset_conv in zip(config.trainingConversations, convs):
            self.assertEqual(config_conv, dataset_conv)
