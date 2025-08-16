import json
import tempfile
from typing import NamedTuple, List

import streamlit as st
from replay_unpack.core.entity import Entity
from replay_unpack.clients.wows.player import ReplayPlayer as WoWSReplayPlayer
from replay_unpack.replay_reader import ReplayReader


class Chat(NamedTuple):
    player_id: int
    namespace: str
    message: str


class ChatPlayer(WoWSReplayPlayer):
    def __init__(self, version: str):
        super(WoWSReplayPlayer, self).__init__(version)
        self._chats = []
        # listen to chat messages
        Entity.subscribe_method_call("Avatar", "onChatMessage", self._on_chat_message)

    def _on_chat_message(self, entity: Entity, player_id, namespace, message, _):
        if player_id in [0, -1]:
            return
        
        self._chats.append(Chat(player_id, namespace, message))

    def get_chats(self) -> List[dict]:
        """
        Get formatted chat messages with player information
        """
        if not hasattr(self, '_battle_controller') or not self._battle_controller:
            return []
            
        players = self._battle_controller._players.get_info()
        formatted_chats = []
        
        for chat in self._chats:
            if chat.player_id in players:
                player = players[chat.player_id]
                player_name = player['name']
                player_clan = player.get('clanTag', '')
                
                formatted_chats.append({
                    'player_id': chat.player_id,
                    'player_name': player_name,
                    'clan_tag': player_clan,
                    'namespace': chat.namespace,
                    'message': chat.message,
                })
        
        return formatted_chats


def parse_replay_file(uploaded_file):
    """
    Parse uploaded replay file and extract chat messages
    """
    # Save uploaded fｓile to temporary location
    with tempfile.NamedTemporaryFile(suffix='.wowsreplay') as tmp_file:
        tmp_file.write(uploaded_file.getvalue())
        tmp_path = tmp_file.name

        # Parse the replay file
        reader = ReplayReader(tmp_path)
        replay = reader.get_replay_data()
        
        # Get version information
        version = replay.engine_data.get('clientVersionFromXml', '').replace(' ', '').split(',')
        
        # Create chat player and process replay
        chat_player = ChatPlayer(version)
        chat_player.play(replay.decrypted_data, strict_mode=True)
        
        return chat_player.get_chats()


def main():
    st.set_page_config(
        page_title="WOWS Chat Viewer",
        page_icon=":ship:",
        layout="wide"
    )
    
    st.title("⚓ World of Warships Chat Viewer")
    st.markdown("Upload a WOWS replay file to view chat messages from the match.")
    
    # Instructions
    with st.expander("ℹ️ How to use"):
        st.markdown("""
        1. **Upload a replay file**: Click the file uploader above and select a `.wowsreplay` file
        2. **Wait for processing**: The app will parse the replay and extract chat messages
        3. **View chat messages**: All chat messages will be displayed with player names and clan tags
        4. **Export chat log**: Download the chat messages as a text file
        """)

    # File uploader
    uploaded_file = st.file_uploader(
        "Choose a replay file", 
        type=['wowsreplay'],
        help="Upload a .wowsreplay file to extract and view chat messages"
    )
    
    if uploaded_file is not None:
        st.info(f"Processing replay file: {uploaded_file.name}")
        
        try:
            with st.spinner("Parsing replay file and extracting chat messages..."):
                chat_messages = parse_replay_file(uploaded_file)
            
            if chat_messages:
                st.success(f"Found {len(chat_messages)} chat messages!")
                
                # Display chat messages
                st.subheader("💬 Chat Messages")
                
                # Create columns for better layout
                col1, col2 = st.columns([3, 1])
                
                with col1:
                    # Display messages using chat message style
                    for chat in chat_messages:
                        avatar = "🔵"
                        name = f"{chat['player_name']}"
                        
                        # Add clan tag if present
                        if chat['clan_tag']:
                            name = f"[{chat['clan_tag']}] {name}"
                        
                        with st.chat_message("user", avatar=avatar):
                            st.write(f"**{name}** `{chat['namespace']}`")
                            st.write(chat['message'])
                            # st.json(chat, expanded=False)
                
                with col2:
                    st.subheader("📊 Statistics")
                    
                    # Count messages by namespace
                    namespace_counts = {}
                    for chat in chat_messages:
                        ns = chat['namespace']
                        namespace_counts[ns] = namespace_counts.get(ns, 0) + 1
                    
                    for namespace, count in namespace_counts.items():
                        st.metric(f"{namespace.title()} Chat", count)
                    
                    # Count unique players
                    unique_players = len(set(chat['player_id'] for chat in chat_messages))
                    st.metric("Active Players", unique_players)
                
                # Download option
                st.subheader("💾 Export Chat")
                
                # Create downloadable text content
                chat_text = []
                for chat in chat_messages:
                    chat_text.append(json.dumps(chat))
                
                chat_content = '\n'.join(chat_text)
                
                st.download_button(
                    label="Download Chat Log",
                    data=chat_content,
                    file_name=f"{uploaded_file.name}_chat.jsonl",
                    mime="text/plain"
                )
                
            else:
                st.warning("No chat messages found in this replay file.")
                
        except Exception as e:
            st.error(f"Error processing replay file: {str(e)}")
            st.error("Please make sure you uploaded a valid WOWS replay file.")


if __name__ == "__main__":
    main()