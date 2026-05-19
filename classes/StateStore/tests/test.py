import os

from classes.StateStore.state_store import StateStore

path = os.path.join(os.getcwd(), "test.db")
print(path)


def wait_for_input():
    input("Press Enter to continue...")
    return 




async def main():   

    ss = StateStore(db_path=path, default_table_name="test")
    await ss.initialize()




    a1 = await ss.get_agent("a1")



    await a1.add("k1.k2.k3" , {"key" : "value"})
    # await a2.replace("k1.k2.k3" , {"key" : "value"}) 


    wait_for_input()
    await a1.replace("k1.k2.k3.1" , 4)


    wait_for_input()
    await a1.replace("k1.k2.k3" , [5,6,7])


    a2 = await ss.get_agent("a2")
    await a2.add("k1.k2.k3" , [1,2,3])
     
    wait_for_input()
    await a2.replace("k1.k2.k3" , {"key" : "value"}) 

    wait_for_input()
    await a1.remove("k1.k2.k3.key")


    print(await a1.get_state_info())
    await ss.cleanup()


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
