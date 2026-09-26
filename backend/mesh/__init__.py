from .manager import MeshManager
from .message import MESSAGE_TYPES, Message, MeshEvent
from .simulation import LocalMeshSimulation
from .transport import MeshTransport

# The manager() factory is deliberately NOT re-exported here. A name in
# this __init__ shadows the submodule of the same name, so re-exporting
# the function made `from backend.mesh import manager` bind the function
# for some callers and the module for others, depending on import order -
# a trap this package fell into once. Import the factory from its module:
#     from backend.mesh.manager import manager

__all__ = [
    "MESSAGE_TYPES",
    "LocalMeshSimulation",
    "MeshEvent",
    "MeshManager",
    "MeshTransport",
    "Message",
]
